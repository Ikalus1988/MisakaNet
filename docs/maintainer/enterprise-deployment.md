# 企业部署 —— 用 GPO / Intune / Jamf / Ansible 推 `misakanet-setup`

> 状态：**已实现**（`packages/misakanet-setup` ≥ 0.5.4）
> 实现：`packages/misakanet-setup/bin/misakanet-setup.mjs`（`--silent` / `--report-json`）
> 测试：`workers/misakanet-setup.test.mjs`（新增 12 项：`--silent` 不打印进度 / 不静音错误 / 报告照样打印 /
> `--report-json` 可 `JSON.parse` **且可被 python `json.load`** / 两种编码逐字段同数据 /
> `--silent --report-json --strict` 的 0·1·2 / 与 `--only`·`--uninstall` 组合）
> 来源：#1767 的 B5 → **#1784**；「数据边界」一节的依据是
> `docs/maintainer/blueprint-and-strategy-review-2026-09-16.md` §2.4（"机构真正会问的三件事"）
> 相关：`docs/maintainer/setup-health-ci.md`（`--report --strict` 接 CI）、`packages/misakanet-setup/README.md`（全部 flag）

本文写给**推工具的人**（IT / 平台工程），不是写给点 `npx` 的那个人。目标只有两个：**静默地装**、
**拿回机器可读的结果**。安全评审要的「数据边界」在第 4 节，那一节可以直接复制给评审。

---

## 1. 一分钟版

```bash
# ① 装（不注册匿名节点，不打印任何进度）
npx -y "@misaka-net/misakanet-setup" --silent --no-register

# ② 出证据（stdout 只有一个 JSON 文档，退出码就是判定）
npx -y "@misaka-net/misakanet-setup" --silent --report-json --strict > machine.json
echo "exit=$?"     # 0 READY / 1 NOT READY / 2 跑不起来
```

| 你的目的 | 命令 |
|---|---|
| 静默安装，不问任何东西 | `--silent --no-register` |
| 机器可读的健康结果 | `--silent --report-json` |
| 让退出码当判定（编排工具用） | 再加 `--strict`（别名 `--ci`） |
| 只装某一种助手 | 再加 `--only claude`（可逗号分隔：`--only claude,codex`） |
| 回滚 | `--uninstall`（精确移除，见 §4.6） |

## 2. 两个新 flag 的契约

### `--silent`：不打印**进度**

被隐藏的：启动横幅（它含本机家目录路径）、`已完成` 的 ✓ 列表、`跳过` 的 · 列表、结尾的「接下来」
引导、`--uninstall` 的「已恢复原状」那一行。

**永远不隐藏的**（这是刻意的：静默不等于哑掉，一个失败得悄无声息的安装器在客户现场无法排查）：

- `! ` 开头的「需要你手动一步」列表 —— 所有错误和所有还需要人做的事都在这；
- 报告本身（`--report` 的 YAML / `--report-json` 的 JSON）；
- `--strict` 的判定行（走 stderr）；
- `--verify` 的结论行。

所以一次**成功**的静默安装，日志是空的；一次**有问题**的静默安装，日志里正好是那几条要处理的事。

### `--report-json`：同一份报告的 JSON 编码

- **stdout 上只有这一个 JSON 文档**，没有别的东西 —— 可以直接 `JSON.parse` 整个流，也可以直接
  `> machine.json`（不进 `tee`，见 §6 坑 1）。
- schema 恒为 `misakanet-setup-report/1`；**字段名与 YAML 报告完全同名**（一份 schema，两种编码），
  区别只是 JSON 保留真实类型（`true`/`false`、数字、数组），YAML 把它们写成不带引号的标量。
- **机器不健康时照样产出**（`verify: "NOT READY"`）—— 那正是要收集数据的那台机器。
- **只读**：和 `--report` 一样，它**不写任何文件、不改任何配置**（也就是它不安装）。要装是另一条
  命令（见 §1 的两步）。这让它天然适合当检测/审计任务，反复跑没有副作用。
- 与 `--report` 同模式、同优先级、同退出码；`--silent` 对两者都不影响。

`--report-json` 的形状（示意，真实值随机器变化；字段名与 YAML 报告一一对应）：

```json
{
  "schema": "misakanet-setup-report/1",
  "setup-version": "0.5.4",
  "os": "windows",
  "distro": "n/a",
  "arch": "x64",
  "node": "v22.22.3",
  "detected-agents": ["claude", "codex"],
  "verify": "NOT READY",
  "endpoint-reachable": false,
  "endpoint-tools": 0,
  "token": "absent",
  "permissions": "ok",
  "hook": "present",
  "voice": "absent",
  "open-items": 2,
  "open-items-detail": ["端点不可达：…", "自动沉淀钩子：缺失 → 重跑安装命令"],
  "tools-visible": {},
  "live-call-evidence": ""
}
```

字段含义、以及**这两个留白字段**（`tools-visible` / `live-call-evidence` 是人手填的，工具从不回读、
也从不参与退出码）见 `docs/maintainer/setup-health-ci.md`。

### 退出码（沿用 #1782 的约定，与 `scripts/check_workflow_scripts.py` 一致）

| 码 | 含义 | 编排里怎么处理 |
|---|---|---|
| `0` | **READY**（`verify: "READY"` 且 `open-items: 0`） | 绿 |
| `1` | **NOT READY**：机器没装好 / 端点不可达 / 还有 `open-items` | 红，**修机器**（`open-items-detail` 每条都带修法） |
| `2` | **跑不起来**：报告根本没生成（stdout 里没有 JSON，stderr 一行原因） | 红，**修工具/看配置**；别把它当"机器不健康"去重装 |

**不加 `--strict` 时永远是 0**（报告是证据不是卡口），要判定就必须显式加。

模式优先级（跟 `--report` 完全一致，别猜）：`--uninstall` > `--report` / `--report-json` > `--verify` >
安装。所以 `--uninstall --report-json` 是**卸载**，不会给你报告 —— 要报告就单独跑一条命令。

## 3. 四种推法

四个片段共同的三个前提，先说清楚（这是四个平台最容易一起踩空的）：

1. **需要 Node ≥ 18**。机器上没有 `npx` 就先推 Node（GPO 用 MSI / Intune 用 Win32 app / Jamf 用
   policy 装 pkg）。装过 Claude Code 或 Codex 的机器通常已经有了。
2. **家目录必须显式给**。GPO 的计算机启动脚本、Intune 的 Platform script、Jamf 的 policy 默认都以
   SYSTEM / root 运行，此时 `~` 不是用户的家目录（Windows 上是 `C:\Windows\System32\config\systemprofile`，
   macOS 上是 `/var/root`），会**装到一个没人读的地方**。所以一律加 `--home <真实用户目录>`。
3. **目标 agent 必须已经跑过至少一次**。安装器按 `~/.claude.json`、`~/.codex`、`~/.hermes`、
   `~/.openclaw`、`~/.codewhale` 是否存在来判断目标，找不到的会**跳过**（那是 `跳过` 列表，属于进度，
   `--silent` 下不打印；一个都没检测到时才会走 `! ` 那段）。所以部署脚本要么用**登录脚本**
   （用户已经跑过 agent），要么把"装"做成**幂等地反复尝试**，而不是开机一次就完事。

### 3.1 GPO（Windows 域）

放一个 `.cmd` 到 `\\<域>\netlogon\misakanet\setup.cmd`，然后用
**用户配置 → Windows 设置 → 脚本 → 登录**（推荐：以用户身份跑，`%USERPROFILE%` 天然正确）或
**计算机配置 → 启动脚本**（以 SYSTEM 跑，必须显式 `--home`）挂上去。

登录脚本版本（推荐，家目录不用猜）：

```cmd
@echo off
setlocal
set LOGDIR=%LOCALAPPDATA%\MisakaNet
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

npx -y "@misaka-net/misakanet-setup" --silent --no-register --home "%USERPROFILE%" ^
  1> "%LOGDIR%\install.log" 2> "%LOGDIR%\install.err"
echo exit=%ERRORLEVEL% > "%LOGDIR%\install.exit"

rem 证据：只读，不写任何配置
npx -y "@misaka-net/misakanet-setup" --silent --report-json --strict --home "%USERPROFILE%" ^
  1> "%LOGDIR%\report.json" 2> "%LOGDIR%\report.err"
echo exit=%ERRORLEVEL% > "%LOGDIR%\report.exit"
endlocal
```

（登录脚本以用户身份跑，所以日志放 `%LOCALAPPDATA%` —— `%ProgramData%` 下的子目录对**其他**用户
未必可写；机器级收集见下面启动脚本版本。）

计算机启动脚本版本 —— 注意 `%USERPROFILE%` 在 SYSTEM 下是
`C:\Windows\System32\config\systemprofile`，**必须替换成真实用户目录**（GPO 无法可靠得知"最终用户
是谁"，这一行得你自己填；填不对就是装进一个没人读的目录，而日志里只显示"成功"）：

```cmd
set LOGDIR=%ProgramData%\MisakaNet
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set TARGETHOME=C:\Users\REPLACE_ME
npx -y "@misaka-net/misakanet-setup" --silent --no-register --home "%TARGETHOME%" ^
  1> "%LOGDIR%\install.log" 2> "%LOGDIR%\install.err"
echo exit=%ERRORLEVEL% > "%LOGDIR%\install.exit"
```

- `%ProgramData%\MisakaNet\*` 就是事后取证的地方；再加一条 GPO 文件收集（或 SCCM/Intune 的
  inventory）把它捞回来即可。
- 计算机启动脚本只跑一次，而"用户还没跑过 agent"是常态（见 §3 前提 3）—— 所以更稳的组合是
  启动脚本负责**推 Node**，登录脚本负责**装接线**（每次登录都跑，幂等，第二次起无改动）。

### 3.2 Intune

**方式 A —— Platform script（Windows）/ Shell script（macOS）**：一次推配置，适合"装完就算"。

`install-misakanet.ps1`（Platform scripts 里选 *Run this script using the logged on credentials: No*
时以 SYSTEM 运行，所以要 `--home`；选 *Yes* 则用 `$env:USERPROFILE`）：

```powershell
$log = Join-Path $env:ProgramData 'MisakaNet'
New-Item -ItemType Directory -Force -Path $log | Out-Null

# SYSTEM 上下文里 $env:USERPROFILE 是 systemprofile：从登录用户反查真实家目录
$who = (Get-CimInstance Win32_ComputerSystem).UserName          # 形如 DOMAIN\user
$targetHome = $env:USERPROFILE
if ($who) {
  $user = $who.Split('\')[-1]
  $profile = Get-CimInstance Win32_UserProfile |
    Where-Object { $_.LocalPath -like "*\$user" } | Select-Object -First 1
  if ($profile) { $targetHome = $profile.LocalPath }
}

& npx -y "@misaka-net/misakanet-setup" --silent --no-register --home $targetHome `
    1> "$log\install.log" 2> "$log\install.err"
Set-Content -Path "$log\install.exit" -Value $LASTEXITCODE
exit 0        # 配置类脚本别因为安装器的退出码反复报错；退出码已经记在 install.exit 里
```

**方式 B —— 可自愈（Proactive remediation）**，这是 `--report-json` 最有用的一处，但**别直接拿
`--strict` 的退出码当检测结果**：`--strict` 判的是"这台机器现在 READY 吗"，而它包含一次
`misakanet.org` 握手 —— 一台忘连 VPN 的笔记本会被判 NOT READY，于是修复脚本被反复触发去重装一个
本来没坏的东西。检测脚本应该读 JSON 里的**分项**再决定：

```powershell
$log = Join-Path $env:ProgramData 'MisakaNet'
& npx -y "@misaka-net/misakanet-setup" --silent --report-json --strict --home $env:USERPROFILE `
    1> "$log\report.json" 2> "$log\report.err"
$rc = $LASTEXITCODE

if ($rc -eq 2) {
  # 报告没生成：工具读不懂本机配置，或环境异常。重装修不了它 —— 留给人看
  Add-Content "$log\needs-human.txt" "$(Get-Date -Format o) exit=2"
  exit 0
}
$report = Get-Content "$log\report.json" -Raw | ConvertFrom-Json
if ($report.verify -eq 'READY') { exit 0 }

# 端点不可达属于"网络/离线"，不是"配置缺失"：在线时它自己会好，重装没有意义
if (-not $report.'endpoint-reachable') { exit 0 }

exit 1        # 真的缺接线 → 让修复脚本去跑 --silent --no-register
```

macOS 端同理：Intune 的 **Shell script**，内容用下面 Jamf 那段的脚本，把日志目录换成
`/Library/Logs/MisakaNet`。

### 3.3 Jamf（macOS）

Policy → Scripts，加一个脚本（以 root 跑，所以脚本自己从 console 用户反查家目录；Jamf 也会把登录
用户名传进 `$3`，两种都行）：

```bash
#!/bin/bash
# MisakaNet MCP 接线：静默安装 + 机器可读报告
set -uo pipefail

LOG=/var/log/misakanet
mkdir -p "$LOG"

# Jamf policy 默认以 root 跑：不要用 $HOME（那是 /var/root）
CONSOLE_USER=$(stat -f%Su /dev/console)
if [ "$CONSOLE_USER" = "root" ] || [ -z "$CONSOLE_USER" ]; then
  echo "no console user; skipping" > "$LOG/skip.log"
  exit 0
fi
TARGET_HOME=$(dscl . -read "/Users/$CONSOLE_USER" NFSHomeDirectory | awk '{print $2}')

# 1) 装（不注册、不打印进度）
npx -y "@misaka-net/misakanet-setup" --silent --no-register --home "$TARGET_HOME" \
  1> "$LOG/install.log" 2> "$LOG/install.err"
echo "exit=$?" > "$LOG/install.exit"

# 2) 报告 + 判定（退出码另存一份，供 EA / inventory 上报）
npx -y "@misaka-net/misakanet-setup" --silent --report-json --strict --home "$TARGET_HOME" \
  1> "$LOG/report.json" 2> "$LOG/report.err"
echo "exit=$?" > "$LOG/report.exit"

exit 0          # 判定在 report.exit / report.json 里，别让 policy 整体标红
```

Jamf **Extension Attribute**（Computer → Extension Attributes → Script），把状态带进 inventory：

```bash
#!/bin/bash
CODE=$(sed -n 's/^exit=//p' /var/log/misakanet/report.exit 2>/dev/null)
case "$CODE" in
  0) echo "<result>READY</result>" ;;
  1) echo "<result>NOT READY</result>" ;;
  2) echo "<result>COULD NOT RUN</result>" ;;
  *) echo "<result>not collected</result>" ;;
esac
```

（`npx` 若来自 nvm，root 的 PATH 里没有它 —— 在脚本里写绝对路径，例如
`/usr/local/bin/npx` 或 `/opt/homebrew/bin/npx`。）

### 3.4 Ansible

```yaml
- name: MisakaNet MCP 接线（不注册、静默、收集 JSON 证据）
  hosts: workstations
  # 不要 become：这些文件要写进**用户自己的**家目录，而且将来是该用户（agent）自己去改它。
  # 以 root 写入会让 agent 之后无法重写自己的配置（也顺手制造一堆 root 属主的 dotfile）。
  become: false
  vars:
    misakanet_home: "{{ ansible_env.HOME }}"
    misakanet_pkg: "@misaka-net/misakanet-setup"
  tasks:
    - name: 安装（只写本机配置文件）
      ansible.builtin.command:
        argv:
          - npx
          - "-y"
          - "{{ misakanet_pkg }}"
          - --silent
          - --no-register
          - --home
          - "{{ misakanet_home }}"
      register: mn_install
      changed_when: false
      failed_when: mn_install.rc not in [0, 1]        # 2 = 工具跑不起来

    - name: 出报告（退出码 0/1/2 就是判定）
      ansible.builtin.command:
        argv:
          - npx
          - "-y"
          - "{{ misakanet_pkg }}"
          - --silent
          - --report-json
          - --strict
          - --home
          - "{{ misakanet_home }}"
      register: mn_report
      changed_when: false
      failed_when: false                               # 判定交给下一句 assert，先把证据留下

    - name: 判定（把 JSON 当数据读，别用 grep）
      ansible.builtin.assert:
        that:
          - mn_report.rc != 2                          # 2 = 报告没生成，那是工具问题不是机器问题
          - ((mn_report.stdout or '{}') | from_json).verify == 'READY'
        fail_msg: >-
          {{ inventory_hostname }}: exit={{ mn_report.rc }}
          {{ ((mn_report.stdout or '{}') | from_json)['open-items-detail']
             | default(['(报告没生成) ' ~ mn_report.stderr]) }}
        success_msg: "{{ inventory_hostname }}: READY"

    - name: 把证据收回控制机（审计留档）
      ansible.builtin.copy:
        content: "{{ mn_report.stdout }}"
        dest: "{{ playbook_dir }}/misakanet-evidence/{{ inventory_hostname }}.json"
        mode: "0644"
      delegate_to: localhost
```

- 判定用 `from_json` 而不是 `stdout is search('READY')`：后者在 `open-items-detail` 里出现
  "NOT READY" 字样时会假阳性。
- `run_once: true` 之类的收敛属于你的编排口味；注意**报告是每台机器一份**，别把它收敛成一份。
- `nvm` 装的 node 不在非交互 shell 的 PATH 里：把 `argv[0]` 换成绝对路径，或用
  `ansible.builtin.shell` 先 `source ~/.nvm/nvm.sh`。
- 想按组织分发**不同的 `--only`**（例如只给装了 Claude Code 的组推 `claude`）就用 host vars；
  注意 `--only` 是安装期的选择器，**报告永远描述整台机器**（`detected-agents` 不会被 `--only` 缩小）。

## 4. 数据边界（给信息安全评审）

先给结论：**这个安装器不上传任何东西。** 它只做两件事——按 agent 自己的配置格式写文件；在
`--report` / `--verify` 时向端点做一次**不带凭据**的握手。报告只写到 stdout，收不收集是**你**的事。
`docs/maintainer/blueprint-and-strategy-review-2026-09-16.md` §2.4 把机构会问的三件事列成了
"数据不出域 / 可审计 / 配额可见"，下面逐条对着答。

### 4.1 留在本机、不出网的

| 数据 | 位置 | 说明 |
|---|---|---|
| 匿名凭据（token） | `~/.misakanet-agent/token`（权限 600） | 只在**你允许注册**时写入；`--report` 只报 `present/absent`，**从不打印值** |
| 自动沉淀钩子 | `~/.misakanet-agent/hook.mjs` | 随 npm 包一起来，不下载 |
| 装机版本戳 | `~/.misakanet-agent/version` | 只含版本号与安装日期，供 14 天一次的升级提醒用 |
| agent 配置改动 | `~/.claude.json`、`~/.claude/{CLAUDE.md,settings.json}`、`~/.codex/config.toml`、`~/.hermes/{config.yaml,.env}`、`~/.openclaw/openclaw.json`、`~/.codewhale/mcp.json` | 全部是**本机文件到本机文件**的写入；原文件先备份成 `<file>.misakanet.bak` |
| 报告本身 | 你的 stdout / 你的日志 | 安装器没有上传报告的代码路径 |

报告里**不含**主机名、IP、用户名、文件内容、环境变量、课程正文；家目录一律写成 `~`。

### 4.2 必须出网的（全部清单，就这两类）

| 目的地 | 什么时候 | 发出去的是什么 | 能不能关 |
|---|---|---|---|
| `registry.npmjs.org`（npm） | `npx` 拉包；`--verify` / `--report*` 时**再多一次**版本查询（仅当已有版本戳） | 常规 npm 请求（包名、User-Agent `misakanet-setup/<版本>`） | 用内网 npm 镜像（`npm_config_registry=https://npm.<内网>/`）；版本查询可换端点：`MISAKANET_REGISTRY_URL` |
| `https://misakanet.org/mcp` | 安装时：注册一次（**除非 `--no-register`**）+ 健康握手 `tools/list`；运行时：agent 每次检索 | 注册：自声明的 `agent_type`/`client_id`；握手：无；检索：**查询词 —— 通常是报错原文的片段** | 注册：`--no-register`；握手：不跑 `--verify`/`--report*` 就不会发生；检索：就是产品本身，关不掉 |

**注意 `--report*` 也会连一次端点**（`tools/list` 握手，用来回答 `endpoint-reachable`）。要一台
机器的报告但完全不碰 `misakanet.org`，就只能不跑报告 —— 没有"离线报告"这条路。

### 4.3 `--no-register` 到底免掉了什么

免掉的：

- **不会**调用 `misakanet_register`，因此**不会有任何注册请求**发到 `misakanet.org`；
- **不会**创建 `~/.misakanet-agent/token`；
- 不会打印（也不会生成）`MISAKANET_CLIENT_ID` 那行提示。

**没有**免掉的（别把它当"离线模式"）：agent 运行时的检索仍然要走 `misakanet.org`，只是走**匿名**通道，
读**不限次数**（2026-09-18 起取消了每日读配额，只剩反爬突发保护——同一地址每分钟的上限，被拒时的说明是
「速度限制、不是配额」）。想要数据完全不出网，得换成 §4.5 的**本地 stdio 形态**（那是另一条接线，
不是这个 flag 能给的）。

### 4.4 审计：报告能回答什么、不能回答什么

**能**：某台机器装了什么版本、什么 OS/架构/Node、检测到哪些 agent、端点当时通不通、token 有没有、
只读工具是否已放行、钩子在不在、还有几项没弄好（`open-items-detail` 逐条带修法）。

**不能**：谁用过、查了什么、命中率多少（那些在服务端事件表里，且是匿名的 —— 见
`docs/agents/repo-operations.md`）；也**无法证明** agent 真的调用了工具，那正是报告最后两个留白字段
（`tools-visible` / `live-call-evidence`）要人补的原因。

**目前没有的**（不要对采购承诺）：服务端**没有**组织级配额、账单视图或按租户的事件导出。
限额只有 IP 级匿名配额；带 token 的调用不计入那个配额，但也没有组织聚合。这是
`blueprint-and-strategy-review-2026-09-16.md` §2.4 明确记着的缺口。

### 4.5 自托管：托管端点**没有**自托管形态；语料可以完全本地跑

诚实回答，因为这是第一个被问到的问题。分三层说，别让采购听成"可以自托管"：

**① `misakanet.org` 的 HTTP 端点是单一托管服务，本仓不提供自托管的部署路径。** 没有一键自托管的
容器/Helm/安装脚本；worker + D1 的抽象确实可以改造（`wrangler.jsonc` + `workers/` 都在仓里），
但那是一条**要自己接的工程线**，不是被支持的形态。`docs/maintainer/blueprint-and-strategy-review-2026-09-16.md`
§2.4 把这件事记成"当前只有托管形态"。

**② 但语料可以完全留内网 —— 用本地 stdio 形态，不出任何网。** clone 仓库后：

```bash
pip install -r requirements.txt        # misakanet-core / mcp / pyyaml / jsonschema
python3 scripts/mcp_server.py         # stdio MCP server，检索本地 lessons/**
```

Claude Code 里的等价配置（注意是 `command` + `args`，不是 `url`）：

```json
{"mcpServers": {"misakanet": {"command": "python3", "args": ["/opt/MisakaNet/scripts/mcp_server.py"]}}}
```

这条路**能满足"数据不出域"**，代价要说清楚：

- **它不是你装的那个东西。** 本安装器写进 agent 配置的是 `url: https://misakanet.org/mcp`；要走本地
  stdio，得由你用配置管理**覆盖**那条 MCP 条目（或在 `--uninstall` 之后自己写），安装器不生成它。
- 语料是 **clone 那一刻的快照**：没有服务端的持续更新、没有匿名额度与写入门禁、也没有 `me_events`
  那种"这条经验被别人复用过"的证据。
- 它需要 **Python 环境**（`pip install -r requirements.txt`），而安装器的卖点之一恰恰是"不需要 Python"。

**③ `MISAKANET_ENDPOINT` 可以把安装器指向你自己的 HTTP 端点**（它会照写进各 agent 配置），
但那个端点得你自己实现、自己保证与 7 个工具的行为兼容 —— 本仓不带它，也不做兼容性承诺。

### 4.6 卸载与回滚

`--uninstall` 精确移除它加过的东西（marker 块、MCP 条目、钩子、权限放行、状态目录），每个改过的
文件都有 `.misakanet.bak` 备份。静默模式下用法一样：

```bash
npx -y "@misaka-net/misakanet-setup" --silent --uninstall
```

### 4.7 给安全评审的一段话（可直接复制）

> MisakaNet 的客户端安装器（`@misaka-net/misakanet-setup`，npm 公开包，零运行时依赖，仅需 Node 18+）
> 在本机做的事：按各 AI 助手自己的配置格式写入一个 MCP 服务器条目与一段提示词规则块，并把原文件备份为
> `*.misakanet.bak`。它不安装常驻服务、不开监听端口、不写系统目录、不需要管理员权限、不上传任何数据
> —— 报告只写到 stdout，由我们自行收集留档。
>
> 出网只有两类：① npm 拉包（可指向内网镜像）；② 对 `https://misakanet.org/mcp` 的 HTTPS 请求。
> 部署时用 `--no-register` 可**完全免除注册**：不发送注册请求、不在本机落任何凭据文件。运行时 AI 助手
> 检索失败经验时会向该端点发送**查询词**（通常是报错原文片段），这是该产品唯一会离开本机的业务数据；
> 除此之外不发送主机名、用户名、IP、文件内容或环境变量。凭据是匿名的化名（`client_id`/`agent_type`
> 均为自声明，不作为归属证据），有效期 30 天，可随时用 `--uninstall` 清除。
>
> 报告（YAML/JSON，schema `misakanet-setup-report/1`）经脱敏设计：家目录写成 `~`，token 只报
> `present/absent`，不含主机名与用户名。
>
> 已知边界（如实说明）：托管的 HTTP 端点**不提供自托管形态**；服务端**没有**组织级配额与审计导出。
> 若要求数据完全不出网，可以改用**本地 stdio 形态**（clone 仓库 + `python3 scripts/mcp_server.py`，
> 只检索本地 `lessons/**`），但那条路径不是本安装器配置的接线，且拿不到服务端的持续更新与复用证据。

## 5. 在你自己的机器上先验一遍

```bash
TMPHOME=$(mktemp -d)
export MISAKANET_ENDPOINT=http://127.0.0.1:9/mcp      # 死端口 = 确定性的 NOT READY

# ① 造一台"装过 agent"的机器，然后静默安装：成功时不该有任何输出
mkdir -p "$TMPHOME/.claude"
printf '{"mcpServers":{}}\n' > "$TMPHOME/.claude.json"
printf '{}\n' > "$TMPHOME/.claude/settings.json"
node packages/misakanet-setup/bin/misakanet-setup.mjs --home "$TMPHOME" --silent --no-register
# → （无输出），exit=0

# ② 报告：JSON 合法吗？退出码对吗？（先落盘再解析：管道会把退出码换成 python 的）
node packages/misakanet-setup/bin/misakanet-setup.mjs --home "$TMPHOME" --silent --report-json --strict \
  1> /tmp/machine.json 2> /tmp/machine.err; echo "exit=$?"
python3 -m json.tool /tmp/machine.json
# → 一份 JSON；exit=1（NOT READY），stderr 一行「--strict：NOT READY（…）→ 退出码 1」

# ③ 2 是怎么来的：一个工具读不懂的 settings.json（注意要先生成钩子，否则走的是"钩子缺失"那条分支）
printf '{"hooks":{"Stop":[{"hooks":5}]}}\n' > "$TMPHOME/.claude/settings.json"
node packages/misakanet-setup/bin/misakanet-setup.mjs --home "$TMPHOME" --silent --report-json --strict; echo "exit=$?"
# → stdout 为空（没有半份 JSON），stderr 一行「报告生成失败 —— 退出码 2」，exit=2

# ④ 一台还没有任何 agent 目录的机器：静默安装照样会说出它做不了什么（这就是"静默不等于哑掉"）
FRESH=$(mktemp -d)
node packages/misakanet-setup/bin/misakanet-setup.mjs --home "$FRESH" --silent --no-register
# → 需要你手动一步（1）:
#      ! 没检测到 Claude Code / Codex / Hermes 的配置目录 → 请先打开一次你要用的那个助手，再回来运行本命令
```

（`mktemp -d` 是为了永远不动你自己的配置。三种退出码在 `setup-health-ci.md` 里还有一份 YAML 版本的复现步骤。）

## 6. 三个坑

1. **别用管道拿退出码**：`npx … --report-json --strict | jq .` 的退出码是 `jq` 的，不是判定的。
   先 `> machine.json`，再单独解析文件（或显式取 `${PIPESTATUS[0]}`）。
2. **`1` 和 `2` 不要合成一类**：`1` 是"这台机器没弄好"（该重装/该排查配置），`2` 是"工具在这台机器上
   跑不起来"。把一个 `2` 当成 `1` 去自愈，会在一台本来没问题的机器上反复重装。
3. **别用 `--silent` 当"日志少一点"的开关**：它会连「需要你手动一步」以外的全部输出一起去掉。
   要"少而全"，用 `--silent --report-json` —— 结构化那份才是给机器看的，`! ` 那些行才是给人看的。

## 7. 相关

- 安装器与全部 flag / 退出码：`packages/misakanet-setup/README.md`
- 把报告接进 CI（GitHub Actions，可复制）：`docs/maintainer/setup-health-ci.md`
- 报告字段与两个留白字段的口径：#1782（`--report --strict`）、本 issue #1784
- 机构侧现状与缺口（数据不出域 / 审计 / 配额）：`docs/maintainer/blueprint-and-strategy-review-2026-09-16.md` §2.4
- 数据流与隐私边界的实现细节：`packages/misakanet-setup/bin/misakanet-setup.mjs` 顶部注释与
  `probeEndpoint()` / `mcpRequest()` 的说明（为什么探测**不带**凭据）
- 自托管 / 完全不出网的替代路径（本地 stdio 端点）：`scripts/mcp_server.py`、`search_knowledge.py`、
  §4.5；语料许可 Apache-2.0（`LICENSE`）
