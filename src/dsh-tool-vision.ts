import { registerTool } from "@deepseek-ai/dsh-tool"
import { join, sep, parse, dirname, basename } from "node:path"
import fs from "node:fs"
import crypto from "node:crypto"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isImageFile(path: string) {
  return /\.(jpe?g|png|gif|webp|bmp|avif|tiff?)$/i.test(path)
}

function md5Hash(filePath: string): string {
  const buf = fs.readFileSync(filePath)
  return `sha256:${crypto.createHash("sha256").update(buf).digest("hex")}`
}

/**
 * Resolve an attachment reference from a session.
 *
 * After the DSH upgrade the `session` object may no longer expose `events`
 * directly – it is sometimes only available through `snapshotEvents()`.
 * This helper covers both shapes so that attachment-based vision calls keep
 * working post-upgrade.
 */
async function lookupAttachment(
  session: any,
  attachmentId: string,
): Promise<{ attachmentId: string; mediaType: string; width?: number; height?: number; bytes?: number } | undefined> {
  // First try the native `events` array when it exists (pre-upgrade shape).
  if ("events" in session) {
    const events = (session.events as any[]) ?? []
    for (const evt of events) {
      const content = evt?.content as any
      if (!content) continue
      if (Array.isArray(content)) {
        for (const part of content) {
          if (part?.type === "image_url" && part?.image_url?.url?.startsWith(attachmentId)) {
            return {
              attachmentId: part.image_url.url,
              mediaType: part.image_url.mime_type ?? "image/jpeg",
              width: part.image_url.width,
              height: part.image_url.height,
              bytes: part.image_url.bytes,
            }
          }
        }
      }
    }
    return undefined
  }

  // Fallback: use snapshotEvents() when `events` property is absent
  // (post-upgrade session shape).
  if (typeof (session as any).snapshotEvents === "function") {
    const events = (session as any).snapshotEvents()
    if (!Array.isArray(events) || events.length === 0) return undefined
    for (const evt of events) {
      const content = evt?.content as any
      if (!content) continue
      if (Array.isArray(content)) {
        for (const part of content) {
          if (part?.type === "image_url" && part?.image_url?.url?.startsWith(attachmentId)) {
            return {
              attachmentId: part.image_url.url,
              mediaType: part.image_url.mime_type ?? "image/jpeg",
              width: part.image_url.width,
              height: part.image_url.height,
              bytes: part.image_url.bytes,
            }
          }
        }
      }
    }
  }

  return undefined
}

async function readAttachment(session: any, attachmentId: string): Promise<Buffer> {
  const ref = await lookupAttachment(session, attachmentId)
  if (!ref) throw new Error(`tool-vision: unknown attachment id "${attachmentId}" (it must come from an image uploaded in this conversation)`)
  if (ref.bytes != null) return Buffer.from(ref.bytes)
  throw new Error(`tool-vision: cannot decode attachment "${attachmentId}" — missing bytes metadata`)
}

// ---------------------------------------------------------------------------
// Tool implementations
// ---------------------------------------------------------------------------

export async function setup(session: any, _ctx: any) {
  registerTool({
    name: "vision_materialize",
    description: "Render an image into a visual prompt (e.g., for multimodal LLM calls). Requires an image uploaded in the current conversation.",
    parameters: {
      type: "object",
      required: ["attachment_id"],
      properties: {
        attachment_id: { type: "string", description: "The attachment ID (sha256:...) of the image to materialize." },
      },
    },
    execute: async ({ attachment_id }: { attachment_id: string }) => {
      const buf = await readAttachment(session, attachment_id)
      const ref = await lookupAttachment(session, attachment_id)
      if (!ref) throw new Error(`tool-vision: unknown attachment id "${attachment_id}"`)
      return {
        kind: "image_materialized",
        attachmentId: ref.attachmentId,
        mediaType: ref.mediaType,
        width: ref.width,
        height: ref.height,
        bytes: buf.toString("base64"),
      }
    },
  })

  registerTool({
    name: "vision_ocr",
    description: "Extract text from an image uploaded in the current conversation.",
    parameters: {
      type: "object",
      required: ["attachment_id"],
      properties: {
        attachment_id: { type: "string", description: "The attachment ID (sha256:...) of the image to OCR." },
      },
    },
    execute: async ({ attachment_id }: { attachment_id: string }) => {
      const buf = await readAttachment(session, attachment_id)
      // Placeholder: real implementation would call an OCR service / model.
      const text = /* @__PURE__ */ "" // TODO: integrate actual OCR pipeline
      return { kind: "ocr_result", text, attachmentId: attachment_id }
    },
  })

  registerTool({
    name: "vision_crop",
    description: "Crop a region from an image uploaded in the current conversation.",
    parameters: {
      type: "object",
      required: ["attachment_id", "x", "y", "width", "height"],
      properties: {
        attachment_id: { type: "string" },
        x: { type: "number" },
        y: { type: "number" },
        width: { type: "number" },
        height: { type: "number" },
      },
    },
    execute: async ({ attachment_id, x, y, width, height }: { attachment_id: string; x: number; y: number; width: number; height: number }) => {
      const buf = await readAttachment(session, attachment_id)
      const ref = await lookupAttachment(session, attachment_id)
      if (!ref) throw new Error(`tool-vision: unknown attachment id "${attachment_id}"`)
      return {
        kind: "cropped_image",
        attachmentId: attachment_id,
        mediaType: ref.mediaType,
        x, y, width, height,
        bytes: buf.toString("base64"),
      }
    },
  })

  registerTool({
    name: "vision_present",
    description: "Read an image from a local file path and register it as an attachment in the conversation.",
    parameters: {
      type: "object",
      required: ["path"],
      properties: {
        path: { type: "string", description: "Absolute or relative path to a local image file." },
      },
    },
    execute: async ({ path }: { path: string }) => {
      const resolved = join(process.cwd(), path)
      if (!fs.existsSync(resolved)) throw new Error(`tool-vision: file not found "${resolved}"`)
      if (!isImageFile(resolved)) throw new Error(`tool-vision: not an image file "${resolved}"`)
      const buf = fs.readFileSync(resolved)
      const hash = md5Hash(resolved)
      const size = buf.length
      const mime =
        resolved.toLowerCase().endsWith(".png") ? "image/png" :
        resolved.toLowerCase().endsWith(".gif") ? "image/gif" :
        resolved.toLowerCase().endsWith(".webp") ? "image/webp" :
        resolved.toLowerCase().endsWith(".bmp") ? "image/bmp" :
        resolved.toLowerCase().endsWith(".avif") ? "image/avif" :
        resolved.toLowerCase().endsWith(".tiff") || resolved.toLowerCase().endsWith(".tif") ? "image/tiff" :
        "image/jpeg"

      // Register the attachment with the session so subsequent vision_materialize etc. can reference it.
      const ref = { attachmentId: hash, mediaType: mime, bytes: size }
      if (typeof (session as any).registerAttachment === "function") {
        ;(session as any).registerAttachment(ref)
      }
      return { ...ref, path: resolved }
    },
  })
}
