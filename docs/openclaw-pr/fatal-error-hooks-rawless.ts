/**
 * Updated src/infra/fatal-error-hooks.ts — 移除 RAW=1 (方案A)
 *
 * Changes from current PR version:
 * - 删除 OPENCLAW_ERROR_HANDLER_RAW env var 读取
 * - 删除 includeRaw / error / isError 变量
 * - 删除 if (includeRaw && isError) payload 扩展块
 * - JSDoc 简化，去掉 RAW 相关说明
 * - payload 固定 4 字段: schemaVersion, reason, timestamp, pid
 */

import { spawn } from "node:child_process";

/** Context passed to fatal-error hooks before the process exits. */
export type FatalErrorHookContext = {
  reason: string;
  error?: unknown;
};

/** Hook that can return one extra diagnostic line for fatal error output. */
export type FatalErrorHook = (context: FatalErrorHookContext) => string | undefined | void;

const hooks = new Set<FatalErrorHook>();

function formatHookFailure(error: unknown): string {
  const name = error instanceof Error && error.name ? error.name : "unknown";
  return `fatal-error hook failed: ${name}`;
}

/** Registers a fatal-error hook and returns an unsubscribe callback. */
export function registerFatalErrorHook(hook: FatalErrorHook): () => void {
  hooks.add(hook);
  return () => {
    hooks.delete(hook);
  };
}

/**
 * If OPENCLAW_ERROR_HANDLER is set, spawns the executable with a
 * structured payload as the first argv entry. The handler must be a
 * path to an executable (not a shell command) — shell expansion is
 * deliberately disabled.
 *
 * Security: `shell: false` prevents command injection via the env var.
 *
 * Privacy: the payload is intentionally limited to non-sensitive fields
 * (schemaVersion, reason, timestamp, pid) to avoid leaking diagnostic
 * details through argv, which is visible to process listings, audit
 * logs, and platform telemetry.
 *
 * Lifetime: the handler runs detached and is `unref()`'d; OpenClaw does
 * not wait for its completion. The payload is delivered atomically as
 * argv[1] during execve, which avoids the parent `process.exit()` <->
 * child stdin drain race that a `stdio: "pipe"` approach would
 * introduce.
 */
function runExternalErrorHandler(context: FatalErrorHookContext): void {
  const handler = process.env.OPENCLAW_ERROR_HANDLER?.trim();
  if (!handler) return;

  try {
    const payload: Record<string, unknown> = {
      schemaVersion: 1,
      reason: context.reason,
      timestamp: new Date().toISOString(),
      pid: process.pid,
    };

    const child = spawn(handler, [JSON.stringify(payload)], {
      stdio: ["ignore", "inherit", "inherit"],
      detached: true,
      shell: false,
    });

    // Async 'error' fires when spawn fails asynchronously (ENOENT, EACCES,
    // etc.). The synchronous try/catch above does not catch it, and a
    // detached + unref()'d child would otherwise let the event bubble to
    // the top-level uncaughtException handler. Swallow it here so a
    // misconfigured handler cannot corrupt OpenClaw's exit pathway.
    child.on("error", () => {
      // Intentionally silent: the primary fatal-error output has already
      // been written, and surfacing the handler's failure here would
      // just look like OpenClaw itself crashed.
    });

    child.unref();
  } catch (err) {
    console.error("[fatal-error-hooks] OPENCLAW_ERROR_HANDLER failed:", String(err));
  }
}

/** Runs registered fatal-error hooks and returns non-empty diagnostic lines. */
export function runFatalErrorHooks(context: FatalErrorHookContext): string[] {
  const messages: string[] = [];
  for (const hook of hooks) {
    try {
      const message = hook(context);
      if (typeof message === "string" && message.trim()) {
        messages.push(message);
      }
    } catch (err) {
      // Fatal output must keep progressing even if a diagnostic hook itself throws.
      messages.push(formatHookFailure(err));
    }
  }

  // External handler is best-effort and never contributes to the in-process
  // diagnostic stream: its job is to ship a structured payload elsewhere.
  runExternalErrorHandler(context);

  return messages;
}

/** Clears registered fatal-error hooks; test-only helper. */
export function resetFatalErrorHooksForTest(): void {
  hooks.clear();
}
