---
{
  "domain": "dsh",
  "title": "DSH Plugin Sidebar and Panel View Registration Contracts",
  "tags": [
    "dsh",
    "plugin",
    "sidebar",
    "mcp"
  ],
  "status": "published",
  "evidence_level": "E1",
  "summary_plain": "DSH插件需在七个扩展席位完成显式注册并遵守启动依赖时序，才能正常挂载侧边栏面板与状态徽章。",
  "trigger": "sidebar acceptance results dsh plugin surface registration",
  "verify": "pytest tests/test_dsh_plugin_surface.py 退出码为 0"
}
---

In DeepSeek Harness (DSH) desktop and web environments, registering a companion plugin into the application shell requires adhering to strict extension point contracts across seven UI injection seats.

## Problem

When installing client-side plugins into DSH profiles (`~/.dsh/profiles/web`), developers report missing panel tabs, unrendered icon glyphs, or boot graph errors:
```
Failed to mount sidebar extension: seat 'sidebar.panellist' unmapped in client bundle.
```
While static contract tests may report green, UI components fail to appear in the left rail or right drawer if registration order is inverted.

## Root Cause

DSH defines seven adjacent extension points for plugin integration:
1. `conversation.view`
2. `sidebar.panellist`
3. `main`
4. `shell.overlay`
5. `sidebar.footer.action`
6. `sidebar.right.pane.tab`
7. `sidebar.right.pane.tab.title`

If a plugin loads before its host bundle (`@deepseek-ai/dsh-web-app`) in the boot graph, or fails to provide an explicit icon registration on `sidebar.panellist` (lines 1839–1847 in client bundles), the web shell ignores the plugin registration and mounts an empty placeholder.

## Fix

1. Share the primary panel component (`MisakanetPanel`) across `conversation.view`, `main`, and `sidebar.right.pane.tab`.
2. Register an explicit 9-line icon component (`MisakanetPanelIcon`) on `sidebar.panellist` to ensure left-rail badge rendering.
3. Verify that host shell dependencies load at lower indices in the profile boot graph prior to mounting downstream plugins.

## Verification

Run the DSH plugin surface contract suite to verify all seven injection points are correctly satisfied:

```bash
pytest tests/test_dsh_plugin_surface.py
```
Expected output:
```
tests/test_dsh_plugin_surface.py::test_extension_seats PASSED (42/42 green)
```
