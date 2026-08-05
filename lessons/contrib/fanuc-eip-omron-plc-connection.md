{"id": "fanuc-eip-omron-plc-connection", "title": "FANUC Robot EtherNet/IP Connection with OMRON PLC", "domain": "fanuc", "subdomain": "plc-communication", "source": "bbs.gongkong.com/d/202112/878050", "status": "draft", "confidence": 0.6, "created": "2026-07-12", "tags": ["fanuc", "ethernet-ip", "eip", "omron", "plc-communication", "hardware-cost"], "quality_score": 50, "problem": "需要将 OMRON PLC 与 FANUC 机器人建立通讯连接。传统方案（如 PROFINET、DeviceNet）需要额外购买通讯硬件卡，增加了系统成本。", "root_cause": "FANUC 机器人的以太网端口为标准配置，无需额外购买硬件即可支持 EtherNet/IP (EIP) 协议。使用 EIP 通讯可有效减少硬件成本，但需要正确配置以太网参数和 EIP 连接。", "solution": "1. 确认 FANUC 机器人固件版本支持 EtherNet/IP\n2. 配置 FANUC 侧以太网参数（IP 地址、子网掩码）\n3. 在 OMRON PLC 侧（CX-Integrator 或 Sysmac Studio）添加 FANUC EIP 设备\n4. 配置 EIP 连接参数（Assembly Instance、连接大小）\n5. 映射 I/O 信号（DI/DO 与 PLC 地址对应）\n6. 测试通讯连接并验证信号收发", "verification": "1. OMRON PLC 编程软件显示 FANUC EIP 设备在线\n2. PLC 写入 DO 信号，FANUC 侧 DI 信号正确响应\n3. FANUC 输出 DO 信号，PLC 侧读取值正确\n4. 通讯无超时或断线报警"}

## FANUC 机器人与 OMRON PLC 的 EtherNet/IP 连接

### 问题描述

在工业自动化项目中，需要将 **OMRON PLC** 与 **FANUC 机器人** 建立通讯连接。常见通讯方案（PROFINET、DeviceNet）通常需要为 FANUC 机器人额外购买专用通讯硬件卡，增加了系统成本。

使用 **EtherNet/IP (EIP)** 协议可以有效降低硬件成本，因为 FANUC 机器人的以太网端口为标准配置，无需额外购买硬件。

### 根因分析

| 通讯方案 | 硬件需求 | 成本 |
|----------|----------|------|
| PROFINET | 需购买 PROFINET 适配卡 | 较高 |
| DeviceNet | 需购买 DeviceNet 适配卡 | 中等 |
| **EtherNet/IP** | **标准以太网端口即可** | **较低** |
| CC-Link | 需购买 CC-Link 适配卡 | 较高 |

FANUC 机器人标准配置的以太网端口原生支持 EtherNet/IP 协议，因此使用 EIP 方案可以**有效减少硬件成本**。

### 修复方法/技术要点

#### 1. 前置条件确认

- FANUC 机器人固件版本需支持 EtherNet/IP（较新版本默认支持）
- OMRON PLC 需支持 EtherNet/IP 主站功能（如 NJ/NX 系列）

#### 2. FANUC 侧配置

- 设置以太网参数：
  - MENU → SETUP → Host Comm → 设置 IP 地址、子网掩码
  - 确保与 OMRON PLC 在同一网段
- 配置 EIP 通讯参数：
  - 设置 Assembly Instance（输入/输出实例号）
  - 配置连接大小（数据字节数）

#### 3. OMRON 侧配置

- 使用 **CX-Integrator** 或 **Sysmac Studio** 软件
- 在 EIP 网络中添加 FANUC 设备
- 配置 EIP 连接参数与 FANUC 侧匹配
- 映射 I/O 地址到 PLC 变量

#### 4. 信号映射

```
FANUC 侧                    OMRON PLC 侧
DI[1-128]  ← EtherNet/IP →  Output 区域
DO[1-128]  → EtherNet/IP →  Input 区域
AI[1-10]   ← EtherNet/IP →  Output 区域（模拟量）
AO[1-10]   → EtherNet/IP →  Input 区域（模拟量）
```

### 验证方式

1. OMRON PLC 编程软件中确认 FANUC EIP 设备状态为**在线**
2. PLC 写入输出信号，在 FANUC 机器人示教器上确认 DI 信号正确响应
3. FANUC 机器人输出 DO 信号，在 PLC 侧确认读取值正确
4. 连续运行测试，确认无 EIP 通讯超时或断线报警
5. 检查通讯延迟满足产线节拍要求

### 来源

- 帖子：[OMRON PLC与FANUC发那科机器人 EIP 连接](https://bbs.gongkong.com/d/202112/878050/878050_1.shtml)
- 作者：hy28，2021-12-24
- 说明：原帖包含附件（需积分下载），技术细节基于帖子主题和 EIP 通讯通用流程整理
