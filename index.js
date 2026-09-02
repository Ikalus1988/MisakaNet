/**
 * MisakaNet DSH plugin entry.
 *
 * MisakaNet is a skill/bundle plugin: the failure-memory skill ships as
 * SKILL.md, bundled via `dsh.bundle.patch` (cordis.patch.yml). This entry
 * provides the package.json `main` target that DSH plugin installers expect,
 * and declares the cordis entry id matching the bundle patch.
 *
 * The plugin itself is inert at runtime — MisakaNet's value is the skill
 * content (SKILL.md) and the MCP endpoints it documents:
 *   - Skill:  SKILL.md (failure-memory search & record workflow)
 *   - MCP:    https://misakanet.org/mcp (search / get_lesson / submit_intake / ...)
 */
export const name = 'misakanet';

/**
 * Mount the plugin into the host.
 * No runtime services are required; the entry exists so the bundle loads
 * cleanly and the skill file is discoverable by agents.
 *
 * @param ctx - cordis host context.
 * @param config - optional plugin config.
 */
export function apply(ctx, config = {}) {
  // Intentionally minimal: MisakaNet ships a skill, not host services.
  // Agents consume SKILL.md (bundled) and the public MCP endpoints above.
}
