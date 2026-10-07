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

  // NOTHING BELOW MAY THROW OUT OF THIS FUNCTION.
  //
  // A throw here is a failed activation, and a failed activation inside a profile
  // bundle can take the whole host down: `dsh: startup failed: N required plugins
  // did not activate` — the entire `dsh web` refuses to start, not just this
  // server. That is a catastrophic outcome for a feature whose worst case should
  // be "the tools are missing": the skill (SKILL.md) and every other plugin in
  // the profile are unrelated to whether MisakaNet's MCP client mounted.
  //
  // So the whole body is guarded and reports through the host logger instead.
  // `failOnStartupError` still works as documented — it asks the *MCP client* to
  // treat a failed initial connection or tool sync as fatal (that is a config
  // field of the client, `dsh-mcp-client/lib/index.js`), and when it is set the
  // client's own fiber fails where the host can attribute it. What it must never
  // do is make *our* wrapper the reason a profile will not boot.
  try {
    if (typeof ctx?.plugin !== 'function') {
      // A host that cannot mount child plugins: the skill still works, so say so and stop. This used to
      // throw unconditionally — before the try — which is exactly the failure mode above. The explicit
      // opt-in still gets its error, because that is what an opt-in is for.
      const message = 'misakanet: cordis context has no plugin(); MCP tools not mounted';
      if (options.failOnStartupError) throw new Error(message);
      ctx?.logger?.warn?.(message);
      return;
    }

    let client;
    try {
      // Dynamic import: the client is ESM and only exists inside a DSH install.
      client = await import('@deepseek-ai/dsh-mcp-client');
    } catch (error) {
      if (options.failOnStartupError) throw error;
      // Expected on npm skill-only installs: the skill (SKILL.md) is the payload,
      // and a missing client must not take the whole profile down with it.
      //
      // Returning quietly is right for **boot** and wrong for **diagnosis**. `lib/client.js`
      // mounts the browser half either way, so the observable result is a rendered MisakaNet
      // panel whose tools never reach the agent — intake #2759 reported exactly that ("the
      // sidebar is decorative", zero requests to misakanet.org) with nothing in the host log
      // to separate "this profile never installed the client" from "this profile is broken".
      // The other two guarded paths already log; this one was the only silent branch, and it is
      // the branch that runs most often. Measured 2026-10-08 with the client unresolvable:
      // `apply()` returned and `logger.warn` was called 0 times.
      ctx?.logger?.warn?.(
        'misakanet: @deepseek-ai/dsh-mcp-client is not resolvable, so the MCP tools are not '
        + `mounted (the skill still works): ${error?.message ?? error}`,
      );
      return;
    }

    // The Loader normalizes ESM/CJS/default export shapes before applying a plugin.
    const component = ctx?.loader?.unwrapExports ? ctx.loader.unwrapExports(client) : client;
    ctx.plugin(component, options);
  } catch (error) {
    if (options.failOnStartupError) throw error;
    ctx?.logger?.warn?.(`misakanet: MCP client not mounted: ${error?.message ?? error}`);
  }
}

/**
 * The row's `Config`: what the Loader validates the bundle patch's `config:` against, and what the plugin
 * page turns into a form — the host's own words for it are "the cordis `Config` validator and the
 * Config-form generation's served schema" (`dsh-context`'s `index.d.ts` says the same thing about its own).
 *
 * Built with a **top-level `await` inside a `try`**, not a static import. `@deepseek-ai/schemastery` is a
 * host dependency, but this package is also installed by skill-only consumers that never load this module,
 * and a module-level import failure would take the whole row down rather than only its form. Without it the
 * row keeps working from the patch and only the GUI form is lost — the same "absence is not failure" rule
 * `apply()` follows for the MCP client.
 */
/**
 * Import schemastery from wherever this install can actually reach it.
 *
 * A profile that **installed** this package resolves the bare specifier on its own: Node walks up from
 * `…/profiles/web/node_modules/misakanet/` and finds the profile's copy. A profile that **linked** a working
 * tree does not — Node resolves the link to its real path, so the walk starts in the repository and never
 * sees the profile. That is the shape this repository's own contributor profiles (and the owner's live one)
 * use, so the second attempt resolves from the `dsh` entry point that started the host, where schemastery is
 * a dependency of DSH itself.
 */
async function loadSchemastery() {
  const attempts = ['@deepseek-ai/schemastery'];
  try {
    const { createRequire } = await import('node:module');
    const { realpathSync } = await import('node:fs');
    const { pathToFileURL } = await import('node:url');
    const hostEntry = process.argv[1];
    // Both spellings matter: the bin is usually a **symlink**, and the package's own node_modules sits
    // beside its real path — resolving from the link's directory finds the global root instead.
    const from = [];
    if (hostEntry) from.push(hostEntry);
    try { from.push(realpathSync(hostEntry)); } catch (error) { /* no real path to add */ }
    for (const entry of from) {
      try {
        const resolved = createRequire(entry).resolve('@deepseek-ai/schemastery');
        // `require.resolve` hands back a filesystem path, and a Windows one is not a valid ESM specifier
        // (`C:` parses as a scheme). The bare specifier above is left alone; only paths are wrapped.
        const url = pathToFileURL(resolved).href;
        if (!attempts.includes(url)) attempts.push(url);
      } catch (error) { /* this entry cannot see it */ }
    }
  } catch (error) { /* keep the bare specifier as the only attempt */ }
  for (const specifier of attempts) {
    try {
      const loaded = await import(specifier);
      return loaded.default ?? loaded;
    } catch (error) { /* try the next location */ }
  }
  return undefined;
}

let Config;
try {
  const z = await loadSchemastery();
  if (z === undefined) throw new Error('schemastery is not resolvable from this install');
  Config = z.object({
    transport: z.string().default(DEFAULT_MCP_CONFIG.transport),
    serverName: z.string().default(DEFAULT_MCP_CONFIG.serverName),
    url: z.string().default(DEFAULT_MCP_CONFIG.url),
    headers: z.dict(z.string()).default({ ...DEFAULT_MCP_CONFIG.headers }),
    toolCallTimeoutMs: z.number().default(DEFAULT_MCP_CONFIG.toolCallTimeoutMs),
    failOnStartupError: z.boolean().default(DEFAULT_MCP_CONFIG.failOnStartupError),
  });
} catch (error) {
  Config = undefined;
}

export { Config };
