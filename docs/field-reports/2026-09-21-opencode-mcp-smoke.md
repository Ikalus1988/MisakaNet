# Field Report: OpenCode MCP Integration Smoke Test

- **Date:** 2026-09-21
- **Client:** OpenCode (`opencode`)
- **Environment:** Windows 11 / Node v24.15.0 / MisakaNet Setup v0.5.6
- **Related Issue:** #1947

---

## 1. Setup Execution

Executed installation targeting OpenCode:
```bash
npx @misaka-net/misakanet-setup@latest --only opencode
```

Output:
```
已完成（3）:
  ✓ 版本戳 → ~/.misakanet-agent/version（0.5.6）
  ✓ 匿名身份：Misaka10489 (token 存 ~/.misakanet-agent/token)
  ✓ OpenCode：注册 MCP → ~/.config/opencode/opencode.json
```

## 2. Verification Run

Executed verification:
```bash
npx @misaka-net/misakanet-setup@latest --verify
```

Output:
```
已完成（4）:
  ✓ 端点可达：https://misakanet.org/mcp（MCP 握手成功，7 个工具）
  ✓ 写入通道：token 已就绪（write_lesson / preflight 可用）
  ✓ OpenCode：MCP 已注册（https://misakanet.org/mcp）
  ✓ 版本：0.5.6（2026-09-21）—— 已是最新

跳过（1）:
  · OpenCode：只能确认"配置已写"，无法确认它是否已加载 → 看 OpenCode 的 MCP 列表复核

结论：READY
```

## 3. Generated Config Verification

Inspected `~/.config/opencode/opencode.json`:
```json
{
  "mcp": {
    "misakanet": {
      "type": "remote",
      "url": "https://misakanet.org/mcp",
      "enabled": true,
      "headers": {
        "Authorization": "Bearer mcp_wMuMofNGay5ywicqgq7xx2h_S-Athr3d",
        "X-MisakaNet-Client": "setup-ef7cc122-9a11-471b-9cb3-7178dd5f5a0a",
        "X-MisakaNet-Agent": "opencode",
        "X-MisakaNet-Os": "win32/x64",
        "X-MisakaNet-Version": "0.5.6"
      }
    }
  }
}
```

## 4. Observations & Potential Traps
1. **JSON vs JSONC**: If the user maintains `opencode.jsonc` with comments, the automated installer does not parse jsonc comments.
2. **XDG_CONFIG_HOME**: If `XDG_CONFIG_HOME` is customized, OpenCode reads `$XDG_CONFIG_HOME/opencode/opencode.json`.
3. **Status Matrix**: Recommended status remains 🔵 vendor-only / 🟡 recipe until end-to-end live chat logs are collected in CI.
