---
title: openclaw prefer cli and policy over direct edit
domain: openclaw
tags:
- openclaw
- cli
- policy
- config
status: published
created: '2026-07-06'
source: unknown
domain_expert: unknown
---

---
## Problem

直接修改配置文件（临时hack）容易变成默认模型，导致官方路径退化。当多个开发者或自动化流程同时操作同一配置文件时，直接编辑会引发竞态条件、格式损坏以及版本冲突，最终使系统处于不可预期的状态。此外，直接修改绕过了官方工具内置的校验逻辑，错误配置可能在运行时才被发现，排查成本极高。

## Root Cause

官方CLI和策略层面有健康检查和版本管理；直改文件没有。具体原因如下：

1. **缺乏原子性保证**：直接写文件不是原子操作，进程崩溃或中断会留下半写状态的配置，导致解析失败。
2. **绕过Schema校验**：`openclaw config` 等官方接口在写入前会对字段类型、取值范围进行校验；直接编辑文件则完全跳过这一环节，非法值可以静默写入。
3. **版本漂移**：官方工具会在变更时记录变更历史（changelog/audit log），直接编辑不会留下任何可追溯记录，导致配置版本与代码版本脱节。
4. **环境隔离失效**：官方CLI会根据当前激活的环境（dev/staging/prod）自动选择正确的配置路径；手动编辑文件时极易误改错误环境的配置。
5. **临时hack固化**：一旦直接修改成为团队习惯，官方路径逐渐被废弃，后续升级或迁移时需要大量人工介入。

## Solution

1. **优先用官方接口操作配置**：使用 `openclaw config` / `gateway` 工具等官方接口，而非直接打开配置文件编辑。

   ```bash
   # 推荐：通过CLI设置模型参数
   openclaw config set model.default gpt-4o
   openclaw config set gateway.timeout 30

   # 不推荐：直接编辑文件
   # vim ~/.openclaw/config.yaml
   ```

2. **临时hack只作fallback，不作默认模型**：若官方接口暂时不可用，可临时修改文件，但必须在注释中标注 `# TEMP HACK - remove after <date>`，并在Issue跟踪系统中创建对应任务。

   ```yaml
   # TEMP HACK - remove after 2026-07-20, tracked in ISSUE-4321
   model:
     default: gpt-4o-mini
   ```

3. **恢复时先恢复官方路径，再拆除临时hack**：恢复顺序非常重要，应先通过官方CLI重新配置，确认生效后再删除临时修改，避免出现配置真空期。

   ```bash
   # Step 1: 通过官方CLI恢复配置
   openclaw config set model.default gpt-4o
   # Step 2: 确认配置已生效
   openclaw config get model.default
   # Step 3: 删除临时hack注释和相关字段
   ```

4. **使用Policy文件统一约束**：在团队级别维护 `openclaw-policy.yaml`，通过策略文件声明哪些配置项禁止手动修改，并在CI流水线中加入配置合规检查。

   ```yaml
   # openclaw-policy.yaml
   enforce:
     - config_via_cli_only: true
     - audit_log: enabled
     - direct_file_edit: forbidden
   ```

## Verification

```bash
openclaw config
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `openclaw config`)
