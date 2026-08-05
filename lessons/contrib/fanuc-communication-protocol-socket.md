{
  "id": "fanuc-communication-protocol-socket",
  "title": "FANUC Robot TCP/IP Socket Communication Protocol and MAPPDK Setup",
  "domain": "fanuc",
  "subdomain": "communication",
  "source": "github.com/torayeff/fanucpy/blob/main/fanuc.md",
  "status": "draft",
  "confidence": 0.85,
  "created": "2026-07-12",
  "tags": ["fanuc", "socket-messaging", "tcp-ip", "mappdk", "network", "karel", "r648"],
  "quality_score": 85,
  "problem": "需要从外部 PC 通过网络与 FANUC 机器人控制器建立通信，实现远程指令下发和状态读取。",
  "root_cause": "FANUC 控制器支持 User Socket Messaging（R648 选件）实现 TCP/IP 通信，但配置步骤分散在多个菜单中，涉及网络配置、服务器设置、KAREL 程序部署等多个环节，容易遗漏。",
  "solution": "按照完整流程配置：网络连接（IP/子网/DHCP）→ 服务器配置（S8 tag/18735 端口/SM 协议）→ Logger 配置（S7 tag/18736）→ MAPPDK 程序部署 → 验证通信。",
  "verification": "1. 控制器 IP 可 ping 通；2. S8 服务器 Current State 为 STARTED；3. 外部客户端能连接 18735 端口；4. MAPPDK 程序在控制器上运行中。"
}

## FANUC Robot TCP/IP Socket Communication Protocol and MAPPDK Setup

### 问题描述

需要从外部 PC（Python/C++/其他）通过 TCP/IP 网络与 FANUC 机器人控制器建立 socket 通信，实现远程运动控制、变量读写、程序调用等功能。FANUC 控制器的通信配置涉及多个菜单层级和系统变量，初学者容易遗漏关键步骤。

### 根因分析

FANUC 控制器的网络通信能力依赖两个关键选件：
- **R632** — KAREL 编程语言（服务端程序运行环境）
- **R648** — User Socket Messaging（TCP/IP socket 通信能力）

通信架构：外部 PC（Python 客户端）→ TCP/IP → 控制器 Socket Server（KAREL 程序）→ 机器人运动/IO

MAPPDK（Manufacturing Application Platform Development Kit）是 FANUC 提供的标准化 socket 服务端实现，使用 S8 服务器 tag 和 18735 端口。

### 修复方法/技术要点

#### 1. 选件兼容性检查

MENU → NEXT → STATUS → Version ID → ORDER FI，确认列表中包含：
- R632 — KAREL
- R648 — User Socket Messaging

ROBOGUIDE 环境：编辑机器人选项时添加 R632 和 R648，然后序列化安装。

#### 2. 网络连接配置

**路径：** MENU → SETUP → Host Comm → TCP/IP

| 配置项 | 真实机器人 | ROBOGUIDE |
|--------|-----------|-----------|
| Robot IP | 192.168.234.2（同网段即可） | 127.0.0.1 |
| Subnet Mask | 255.255.255.0 | 255.255.255.0 |
| DHCP Enable | False | False |
| Host Name | 主机电脑 IP | 主机电脑 IP |

配置完成后按 **INIT** 激活。

#### 3. MAPPDK Server 配置（S8, 端口 18735）

**步骤 1 — 设置端口系统变量：**
MENU → NEXT → SYSTEM → Variables → 选择 `$HOSTS_CFG` → 进入第 8 项 → 设置 `$SERVER_PORT = 18735`

**步骤 2 — 配置服务器：**
MENU → SETUP → Host Comm → SHOW → Servers → 选择 S8

| 配置项 | 值 |
|--------|-----|
| Protocol | SM |
| Port | 18735 |
| Startup State | START |
| Current State | STARTED（需手动 ACTION → DEFINE → START） |

#### 4. MAPPDK Logger 配置（S7, 端口 18736）

与 Server 配置相同流程，使用 S7 作为服务器 tag，端口 18736。

#### 5. MAPPDK 程序文件部署

将以下文件通过 USB 或 FTP 复制到控制器：

| 文件 | 说明 |
|------|------|
| mappdk.ls | 主程序，从示教器运行，启动 server + logger |
| mappdk_server.pc | KAREL 服务端程序 |
| mappdk_logger.pc | KAREL 日志程序 |
| mappdk_move.ls | 运动控制 TP 程序 |
| mappdk_movel.ls | 直线运动 TP 程序 |

运行方式：示教器按 SELECT → 找到 MAPPDK → 在 T1/T2 或 AUTO 模式运行。

#### 6. 保留资源

| 资源 | 用途 |
|------|------|
| USER FRAME 8, TOOL FRAME 8 | MAPPDK 专用坐标系 |
| R[81] | 速度 |
| R[82] | 加速度 |
| R[83] | 连续运动值 |
| PR[81] | 位置/关节值存储 |

#### 7. 通信协议概要

Python 客户端（fanucpy）与 MAPPDK 服务端之间的协议：
- 连接：TCP socket 连接到 `host:18735`
- 指令格式：结构化文本指令（命令名 + 参数）
- 响应格式：状态码 + 返回数据
- 支持的操作：move（joint/pose）、get_curpos、get_curjpos、set_rdo、get_rdo、call_prog 等

#### 8. 故障排除

**Python 脚本挂起或报错：**
1. 示教器按 FCTN → ABORT ALL 终止所有程序
2. 重新运行 MAPPDK

**常见问题：**
- IP 不在同一子网 → 检查网络配置
- 端口 18735 不通 → 检查 S8 服务器状态是否为 STARTED
- KAREL 程序无法运行 → 检查 R632/R648 选件是否安装
- 连接后无响应 → 检查 MAPPDK 主程序是否在运行

### 验证方式

1. 从 PC ping 控制器 IP（如 192.168.234.2）通
2. 控制器上 S8 服务器 Current State 显示 STARTED
3. `telnet controller_ip 18735` 或 Python socket 连接成功
4. MAPPDK 程序在示教器 SELECT 列表中可见且可运行
5. Python 端 `robot.connect()` 返回成功，`robot.get_curpos()` 返回数据

### 来源

- GitHub: torayeff/fanucpy — MAPPDK Driver 安装文档 (fanuc.md)
- FANUC 控制器手册：Host Comm / Socket Messaging 配置章节
