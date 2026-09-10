/**
 * MisakaNet DSH plugin entry.
 *
 * MisakaNet is a skill library, not a Cordis entry. The failure-memory skill
 * ships as SKILL.md (top-level + skills/misakanet/) and is discoverable by
 * any DSH profile that lists `misakanet` as a dependency. This entry provides
 * the package.json `main` target that DSH plugin installers expect and a
 * no-op `apply()` so profile reconciliation succeeds without ever inserting
 * a duplicate Cordis Loader entry.
 *
 * MisakaNet's runtime value is the skill content and the MCP endpoints it
 * documents:
 *   - Skill:  SKILL.md (failure-memory search & record workflow)
 *   - MCP:    https://misakanet.org/mcp (search / get_lesson / submit_intake / ...)
 *
 * About `dsh.bundle.patch` (history matters here): an early version declared a
 * Cordis insert for `id: misakanet`, and dsh.so's l5-web-smoke profile saw the
 * same insert applied twice in its sandbox (Cordis Loader: "duplicate loader
 * entry id"), which cascaded into L5.2 "plugin tree failed to load" and the
 * dependent L5.3 "HTTP endpoint served" failure. The patch was therefore dropped
 * for a while, which made the package install as a plain library with no plugin
 * function at all (the state dsh.so reported against v2.26.0).
 *
 * As of 2026-09-05 the bundle declares `dsh.bundle.patch` again, pointing at
 * cordis.patch.yml — with a structurally different insert: a single row with the
 * bundle-unique id `misakanet-mcp` (never `misakanet`) and
 * `failOnStartupError: false` so a profile without the python server (npm
 * skill-only installs) degrades to a disconnected row instead of failing boot.
 * `apply()` below stays a no-op: the Loader contribution comes from the patch,
 * not from this entry, which keeps duplicate insertion impossible.
 */
export const name = 'misakanet';

/**
 * Mount the plugin into the host.
 * No runtime services are required. Keeping the entry minimal preserves
 * the dsh plugin install contract while avoiding any Loader contribution.
 *
 * @param ctx - cordis host context (unused; preserved for the install contract).
 * @param config - optional plugin config (unused).
 */
export function apply(ctx, config = {}) {
  // Intentionally minimal: MisakaNet ships a skill, not host services.
  // Agents consume SKILL.md (bundled alongside the package) and the public
  // MCP endpoints above. Any state we might inject here would only widen
  // the surface area that dsh.so's L5 sandbox could trip on.
}
