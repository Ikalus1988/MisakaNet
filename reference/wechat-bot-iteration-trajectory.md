---
title: "微信机器人方案迭代轨迹 —— wxauto 安装 + 版本兼容"
domain: devops
source: opus4.6
created: 2026-04-21
status: reference
type: iteration-trajectory
related_lessons:
  - "wxauto-必须在-windows-python-下安装"
  - "wcferry-微信版本锁定"
  - "rag-三通道-llm-容灾方案"
---

# 微信机器人方案迭代轨迹

> Opus 4.6 在开发微信机器人过程中，经历了多次方案迭代。
> 记录这些迭代的触发条件、决策反转过程、和最终收敛结果。

---

## 迭代一：wxauto 安装路径（α → β → γ → δ）

**背景**：需要在 Windows 上安装 wxauto 库，用于操控微信桌面客户端。

### α 方案：pip install wxauto

用户执行：
```powershell
pip install wxauto
```

结果：失败。
```
ERROR: Could not find a version that satisfies the requirement wxauto
```

Opus 根因判断：wxauto 是社区维护库，可能从 PyPI 下架或改名。

**决策反转**：试下一个方案。

### β 方案：升级 pip 后重试

```powershell
python.exe -m pip install --upgrade pip
pip install wxauto requests
```

结果：仍然失败（同上）。

**决策反转**：放弃 PyPI，切到 GitHub 源码安装。

### γ 方案：pip install git+https://github.com/cluic/wxauto.git

```powershell
pip install git+https://github.com/cluic/wxauto.git requests
```

结果：失败。
```
ERROR: Failed to clone — git not found
```

Opus 根因判断：Windows 默认未安装 git。

**决策反转**：不用 git，直接下载 ZIP。

### δ 方案：下载 ZIP + pip install local

```powershell
Invoke-WebRequest -Uri "..." -OutFile "$env:TEMP\wxauto.zip"
Expand-Archive -Path "$env:TEMP\wxauto.zip" -DestinationPath "$env:TEMP\wxauto" -Force
pip install "$env:TEMP\wxauto\wxauto-master" requests
```

结果：
```
ERROR: Invalid requirement — Expected semicolon
```

Opus 根因判断：GitHub 默认分支名为 `main` 而非 `master`，路径错误。

最终修复（δ-final）：
```powershell
pip install "$env:TEMP\wxauto\wxauto-main" requests
```

结果：✅ 成功。

**收敛条件**：避开所有网络依赖（git/PyPI），本地解压安装。

---

## 迭代二：微信版本兼容（α → β → γ）

**背景**：wxauto 启动后报错，微信窗口无法匹配。用户微信版本为 3.9.12.56。

### α 方案：wxauto 直接使用

用户运行 `python wxauto_bot.py` → 找不到微信窗口。

Opus 诊断：wxauto 通过类名定位微信窗口，用户的微信版本类名与 wxauto 内置的不匹配。

```
发现点：
wxauto 内置类名对应 WeChat 3.9.11.17
用户版本 3.9.12.56 → 类名已变
```

### β 方案：切换 wcferry

Opus 提出替代方案 wcferry（DLL 注入式，稳定性更高）。

```python
# wcferry 方案
pip install wcferry
# 需要精确微信版本 3.9.12.51
# 防火墙端口 10086
# 从 WSL2 连接 Windows 的 TCP 通信
```

用户操作后发现问题：
1. 微信 3.9.12.51 被腾讯封锁，无法登录
2. 降级方案不可行

**决策反转**：wcferry 方案废弃，回到 wxauto。

### γ 方案：修复 wxauto 类名

Opus 改为修正 wxauto 的窗口类名匹配：

```python
# 探测用户微信的实际类名
import win32gui
win32gui.EnumWindows(lambda h, _: print(
    f'{h} | {win32gui.GetClassName(h)} | {win32gui.GetWindowText(h)}'
), None)
```

发现用户微信 4.x 的类名为 `Qt51514QWindowIcon`（新版微信架构变更）。

修复方式：更新 wxauto 配置中的窗口类名列表，加入新版类名。

结果：✅ 成功。

**收敛条件**：不换方案，fix 现有方案的接口适配。

---

## 迭代模式总结

| 阶段 | 触发条件 | Opus 决策 | 反转原因 |
|------|---------|----------|---------|
| α→β | PyPI 找不到包 | 升级 pip 重试 | 根源不是 pip 版本 |
| β→γ | pip install 失败 | 切 GitHub 源码 | 环境缺 git |
| γ→δ | git clone 失败 | 下载 ZIP 本地安装 | 分支名猜错 (master→main) |
| δ→✅ | 路径错误 | 修正分支名 | — |
| α→β | 类名不匹配 | 换 wcferry 方案 | 微信版本封锁无法降级 |
| β→γ | 降级微信不可行 | 回 wxauto + 修类名 | — |

**关键规律**：Opus 4.6 在每次方案失败后的处理模式：
1. 不是原地修，而是先判断"当前路径是否值得继续"
2. 如果方向性错误（如 wcferry 的版本锁定不可解），果断回退换方案
3. 如果只是执行细节错（如 ZIP 路径），修正后续继续
4. 每次决策反转都附带了判断依据，而非盲目尝试

---

## 对后续 agent 的建议

接手微信机器人维护时，如果遇到类似问题：
1. 先确认微信版本（`关于微信`），与 wxauto/wcferry 的兼容列表对照
2. wxauto 失败 → 优先检查窗口类名，不急着换方案
3. wcferry 方案需确认目标微信版本未被封锁
4. 安装失败时优先查 pip 源/GitHub 可达性/分支名，这三个点覆盖了 90% 的安装问题
