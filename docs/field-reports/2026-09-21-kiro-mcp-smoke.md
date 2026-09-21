# Field Report: Kiro MCP Integration Smoke Test

- **Date:** 2026-09-21
- **Client:** Kiro (`kiro`)
- **Environment:** Windows 11 / Node v24.15.0 / MisakaNet Setup v0.5.6
- **Related Issue:** #1947

---

## 1. Setup Execution

Executed installation targeting Kiro:
```bash
node packages/misakanet-setup/bin/misakanet-setup.mjs --only kiro
```

Output:
```text
MisakaNet 安装程序（npx 版）
家目录：C:\Users\lnhho

已完成（3）:
  ✓ 版本戳 → C:\Users\lnhho\.misakanet-agent\version（0.5.6）
  ✓ 匿名身份：Misaka10492（token 存 C:\Users\lnhho\.misakanet-agent\token，权限 600）
  ✓ Kiro：注册 MCP → C:\Users\lnhho\.kiro\settings\mcp.json

需要你手动一步（1）:
  ! Kiro：重启 Kiro 后用它的 MCP 面板复核 misakanet（Kiro 还支持 disabled / autoApprove 字段）

跳过（1）:
  · Kiro：没有规则块与钩子（它读 .kiro/steering/*.md（steering 文件），安装器不写别人的规则文件）→ 想让 Kiro 主动去查，把规则加进 .kiro/steering/
```

## 2. Verification Run

Executed verification:
```bash
node packages/misakanet-setup/bin/misakanet-setup.mjs --verify
```

Output:
```text
已完成（4）:
  ✓ 端点可达：https://misakanet.org/mcp（MCP 握手成功，7 个工具）
  ✓ 写入通道：token 已就绪（write_lesson / preflight 可用）
  ✓ Kiro：MCP 已注册（https://misakanet.org/mcp）
  ✓ 版本：0.5.6（2026-09-21）—— 已是最新

跳过（1）:
  · Kiro：只能确认"配置已写"，无法确认它是否已加载 → 用 Kiro 的 MCP 面板复核
```

## 3. Generated Config Verification

Inspected `~/.kiro/settings/mcp.json`:
```json
{
  "mcpServers": {
    "misakanet": {
      "url": "https://misakanet.org/mcp",
      "headers": {
        "Authorization": "Bearer mcp_rNC0cRUInL_qfAVnQ6a2HaYrYv9fEwRf",
        "X-MisakaNet-Client": "setup-bb5a4d29-36bb-4bf9-94c2-ff2b2a97d12b",
        "X-MisakaNet-Agent": "kiro",
        "X-MisakaNet-Os": "win32/x64",
        "X-MisakaNet-Version": "0.5.6"
      }
    }
  }
}
```

## 4. Observations & Potential Traps

1. **Config Key `url` vs `serverUrl`:**
   Kiro requires a bare `url` field inside `mcpServers.<server_name>`. Providing `serverUrl` or `endpoint` causes silent failure without error notifications in Kiro's MCP panel.
2. **AutoApprove Capability:**
   Kiro supports an optional `"autoApprove": ["misakanet_search"]` property within each server block to allow silent non-intrusive preflight searches.
3. **Steering Location:**
   Kiro steering files reside in workspace `.kiro/steering/*.md`. The global installer intentionally does not touch project steering rules to preserve repository isolation.
4. **Status Matrix:**
   Recommended status remains 🔵 **vendor-only** (or 🟡 **recipe** for automated installer & configuration structure). The matrix file `docs/integrations/status.md` is kept unedited per maintainer guidelines.
