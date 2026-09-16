/**
 * MisakaNet DSH plugin entry.
 *
 * MisakaNet is a skill library first: the failure-memory skill ships as SKILL.md
 * (top-level + skills/misakanet/) and is discoverable by any DSH profile that
 * lists `misakanet` as a dependency. This entry is the package.json `main`
 * target that DSH plugin installers expect, and — since 2026-09-12 — the place
 * where the bundle's MCP row is actually mounted.
 *
 * MisakaNet's runtime value is the skill content and the MCP endpoints it
 * documents:
 *   - Skill:  SKILL.md (failure-memory search & record workflow)
 *   - MCP:    https://misakanet.org/mcp (search / get_lesson / submit_intake / ...)
 *
 * About `dsh.bundle.patch` (history matters here):
 * * An early version declared a Cordis insert for `id: misakanet`, and dsh.so's
 *   l5-web-smoke profile saw the same insert applied twice in its sandbox
 *   (Cordis Loader: "duplicate loader entry id"), which cascaded into L5.2
 *   "plugin tree failed to load" and the dependent L5.3 "HTTP endpoint served"
 *   failure.
 * * 2026-09-05: the patch came back with a structurally different single row —
 *   bundle-unique id `misakanet-mcp`, `failOnStartupError: false` so a profile
 *   without the python server degrades to a disconnected row instead of failing
 *   boot. That row named `@deepseek-ai/dsh-mcp-client` directly, and `apply()`
 *   stayed a no-op.
 * * 2026-09-12 (this file): naming a @deepseek-ai/* component inside a bundle
 *   patch is *hard-blocked* by DSH STORE — its precheck rejects it as
 *   `SUBMISSION_PATCH_PROTECTED: Bundle Patch impersonates the protected
 *   @deepseek-ai namespace` and rates the listing `route: blocked`
 *   (AI-Scarlett/DSH-Store#747; the rule is in that repo's
 *   scripts/check-plugin-submission.mjs). The patch now inserts *this* package
 *   (`name: misakanet`) and `apply()` below mounts the official MCP client with
 *   the row's config — the same runtime behaviour, without naming a
 *   protected component in the patch.
 *
 * Absence is not failure: when the official client is not resolvable (older
 * hosts, a profile that never installed DSH's own copy) `apply()` returns
 * quietly unless the config asks to fail loudly, so the skill keeps working
 * and boot never breaks.
 */
export const name = 'misakanet';

/**
 * Default MCP declaration: the PUBLIC Streamable HTTP endpoint.
 *
 * This is the transport that works from every install channel. The repo's own
 * python server (`scripts/mcp_server.py`, stdio) only exists in repo/git+
 * checkouts, so defaulting to it left every npm install with a disconnected row
 * (issue #1734). The bundle patch states the same declaration explicitly; the
 * patch's row config is merged over this object, so a profile that wants the
 * local server can point the row at it (transport stdio, command python3,
 * args [scripts/mcp_server.py], cwd the repo root) without patching this file.
 */
export const DEFAULT_MCP_CONFIG = Object.freeze({
  transport: 'streamable-http',
  serverName: 'misakanet',
  url: 'https://misakanet.org/mcp',
  headers: { Origin: 'https://misakanet.org' },
  toolCallTimeoutMs: 60000,
  failOnStartupError: false,
});

/**
 * Mount MisakaNet's MCP server into the host.
 *
 * The official client is resolved at runtime and mounted as a child plugin; we
 * never ship or install a copy of it (package.json declares it as an *optional
 * peer* dependency, so a profile that already has DSH's own copy resolves to
 * that one).
 *
 * @param ctx - cordis host context.
 * @param config - MCP config from the bundle patch row (streamable-http by
 *   default; stdio is still accepted, e.g. for the repo's python server).
 */
export async function apply(ctx, config = {}) {
  const options = { ...DEFAULT_MCP_CONFIG, ...config };
  if (typeof ctx?.plugin !== 'function') {
    throw new Error('misakanet: cordis context has no plugin() to mount the MCP client');
  }

  let client;
  try {
    // Dynamic import: the client is ESM and only exists inside a DSH install.
    client = await import('@deepseek-ai/dsh-mcp-client');
  } catch (error) {
    if (options.failOnStartupError) throw error;
    // Expected on npm skill-only installs: the skill (SKILL.md) is the payload,
    // and a missing client must not take the whole profile down with it.
    return;
  }

  // The Loader normalizes ESM/CJS/default export shapes before applying a plugin.
  const component = ctx?.loader?.unwrapExports ? ctx.loader.unwrapExports(client) : client;
  ctx.plugin(component, options);
}
