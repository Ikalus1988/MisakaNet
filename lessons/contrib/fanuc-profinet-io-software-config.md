{
  "id": "fanuc-profinet-io-software-config",
  "title": "FANUC Robot PROFINET IO Configuration with PFN-CT Software",
  "domain": "fanuc",
  "subdomain": "profinet-io",
  "source": "bbs.gongkong.com/d/202311/912784",
  "status": "draft",
  "confidence": 0.6,
  "created": "2026-07-12",
  "tags": ["fanuc", "profinet", "io", "pfn-ct", "plc", "fieldbus", "configuration"],
  "quality_score": 60,
  "problem": "FANUC 机器人需要与 PROFINET IO 主站（如西门子 PLC）通信，需要专用配置软件来设置 PROFINET IO 从站参数。",
  "root_cause": "FANUC 机器人作为 PROFINET IO 从站时，需要使用专用的 PFN-CT（PROFINET Configuration Tool）软件在 PC 端配置 GSD 文件、IO 模块映射等参数，然后下载到控制器。该软件不随控制器出厂提供，需要单独获取。",
  "solution": "使用 PFN-CT V1.0.14 软件配置 FANUC 机器人的 PROFINET IO 通信参数。该软件为 PC 端工具，用于配置从站设备参数并生成配置文件。",
  "verification": "1. PFN-CT 软件安装并能正常启动；2. 能加载 FANUC 机器人的 GSD 文件；3. IO 模块配置完成并下载到控制器；4. PLC 端能识别 FANUC PROFINET IO 从站并建立通信。"
}

## FANUC Robot PROFINET IO Configuration with PFN-CT Software

### 问题描述

FANUC 工业机器人在汽车焊装等场景中需要通过 PROFINET IO 协议与 PLC（如西门子 S7-1200/1500）进行 IO 通信。配置 PROFINET IO 从站需要专用的配置软件，但该软件不是 FANUC 控制器的标准附件，需要单独获取。

### 根因分析

PROFINET IO 是工业以太网现场总线协议，FANUC 机器人作为从站设备接入 PROFINET 网络时：

1. **需要 GSD 文件**：描述 FANUC 机器人 PROFINET 从站的设备特性（厂商 ID、设备型号、支持的 IO 模块等）
2. **需要配置工具**：PFN-CT（PROFINET Configuration Tool）是 FANUC 提供的 PC 端配置软件
3. **配置流程**：在 PC 上配置 IO 模块映射 → 生成配置文件 → 下载到控制器 → PLC 侧添加从站设备

### 修复方法/技术要点

#### 1. PFN-CT 软件信息

| 项目 | 说明 |
|------|------|
| 软件名称 | PFN-CT (PROFINET Configuration Tool) |
| 版本 | V1.0.14（截至 2023-11） |
| 平台 | Windows PC |
| 用途 | 配置 FANUC 机器人 PROFINET IO 从站参数 |
| 获取方式 | FANUC 技术支持或工控论坛资源 |

#### 2. PROFINET IO 配置一般流程

虽然原帖未提供详细步骤，FANUC PROFINET IO 配置的典型流程如下：

**PC 端（PFN-CT）：**
1. 安装 PFN-CT 软件
2. 导入 FANUC 机器人 GSD 文件
3. 配置 IO 模块（输入/输出字节数、数据映射）
4. 生成配置文件

**控制器端：**
5. 将配置文件传输到 FANUC 控制器
6. 配置控制器的 PROFINET 从站参数
7. 设置 IP 地址和设备名称

**PLC 端（如西门子 TIA Portal）：**
8. 导入 FANUC GSD 文件
9. 在硬件配置中添加 FANUC 从站设备
10. 配置 IO 地址映射
11. 下载 PLC 配置并建立通信

#### 3. 版本说明

论坛用户反馈存在多个版本的 PFN-CT 工具。不同版本可能对应不同控制器固件版本，使用时需注意版本兼容性。用户"枫红一刀流"提到需要旧版本的情况，说明并非新版本总能替代旧版本。

#### 4. 相关背景

FANUC 机器人支持多种现场总线协议：
- PROFINET IO（西门子生态）
- EtherNet/IP（罗克韦尔生态）
- CC-Link（三菱生态）
- DeviceNet

每种协议都有对应的配置工具和选件要求。PROFINET IO 是中国市场最常见的选择之一，特别是在使用西门子 PLC 的汽车焊装线上。

### 验证方式

1. PFN-CT 软件在 Windows PC 上安装并正常启动
2. 能正确加载 FANUC 机器人 GSD 文件，显示设备信息
3. IO 模块配置完成，输入/输出字节数与实际需求匹配
4. 配置文件成功下载到 FANUC 控制器
5. PLC 端（如 TIA Portal）能识别 FANUC 从站，PROFINET 通信状态为绿色（运行中）
6. PLC 读写 FANUC IO 数据正确

### 来源

- 工控网论坛: bbs.gongkong.com/d/202311/912784 — FANUC机器人配置profinet IO的软件
- 作者: snowei sun, 2023-11-20
- 注意：原帖主要是软件分享帖，详细配置步骤需参考 FANUC 官方 PROFINET IO 配置手册
