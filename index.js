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
 * Why no `dsh.bundle.patch`? Earlier versions declared a Cordis insert for
 * `id: misakanet`. dsh.so's l5-web-smoke profile saw the same insert applied
 * twice in its sandbox (Cordis Loader: "duplicate loader entry id"), which
 * cascaded into L5.2 "plugin tree failed to load" and the dependent L5.3
 * "HTTP endpoint served" failure. Dropping the patch yields a plain
 * library — installable by `dsh plugin add misakanet`, but never registered
 * as a Loader entry, so duplicate-id collisions are structurally impossible.
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
