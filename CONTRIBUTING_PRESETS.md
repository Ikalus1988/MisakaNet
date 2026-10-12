# Guidelines for Creating Agent Presets (DSH)

To prevent "Self-Lock" incidents (where an agent loses all file-system tools during a hot-reload), follow these strict protocols when modifying `profile.patch.yml` or creating new presets.

## 1. The "Tool-Surface" Integrity Rule
A preset is considered **invalid** if it changes the System Prompt but fails to provide the necessary toolset. 

**Verification Checklist:**
- [ ] **System Prompt:** Does the new persona appear in the conversation?
- [ ] **Tool Availability:** Are `pwsh`, `write`, `read`, and `glob` still present in the tool list?

**If the persona is active but tools are missing (e.g., only MCP tools remain), the preset is broken. IMMEDIATELY rollback using your backup.**

## 2. Avoid "Copy-Paste" Plugin Bloat
Do not blindly copy the `plugins` list from the `standard` preset. 
- The `standard` preset relies on a specific combination of `agent-plane` and `host-plane` registrations.
- When creating a custom preset, explicitly define only the plugins you need.
- **Rule of Thumb:** Every plugin added must be justified. If you don't know which layer (agent or host) provides the tool implementation, do not include it.

## 3. Safe Hot-Reload Workflow
**NEVER modify `cordis.patch.yml` (or any active profile patch) within the same session you are currently using for critical tasks.**

**Correct Workflow:**
1. **Backup:** Create a timestamped backup: `cp cordis.patch.yml cordis.patch.yml.bak-<timestamp>`.
2. **Prepare Emergency Script:** Write a PowerShell/Bash command to restore the backup and hand it to the user/agent *before* applying the patch.
3. **Isolated Modification:** Apply the patch in a separate terminal or a new, independent session.
4. **Validation:** Verify the tool-surface in the new session before resuming work in the old one.

## 4. Emergency Recovery (The "Deadlock" Scenario)
If you enter a state where the agent says `unknown tool` for `write` or `pwsh`:
- **Do not attempt to fix it via the agent.** The agent's "hands" (tools) have been removed.
- **Manual Intervention Required:** You must manually execute the rollback in your OS terminal:
  ```powershell
  Copy-Item cordis.patch.yml.bak-<timestamp> cordis.patch.yml -Force
  ```
- **Restart the session** to re-initialize the tool-surface.

## 5. Performance Note
When inspecting profiles, avoid recursive scans of large directories (e.g., `C:\Users\Admin\.dsh`). This can cause the agent to hang during the tool-discovery phase.
