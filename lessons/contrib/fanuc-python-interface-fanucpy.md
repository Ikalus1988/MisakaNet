{
  "id": "fanuc-python-interface-fanucpy",
  "title": "FANUC Robot Python Control via fanucpy Library",
  "domain": "fanuc",
  "subdomain": "python-interface",
  "source": "github.com/torayeff/fanucpy",
  "status": "draft",
  "confidence": 0.8,
  "created": "2026-07-12",
  "tags": ["fanuc", "python", "fanucpy", "socket-messaging", "robot-control", "uop-sop"],
  "quality_score": 80,
  "problem": "需要从 Python 端控制 FANUC 机器人运动、查询状态、操作夹爪和数字 IO，但 FANUC 控制器原生不支持 Python 接口。",
  "root_cause": "FANUC 控器运行 KAREL/TP 语言，不直接支持 Python。需要一个中间层：Python 客户端通过 TCP/IP Socket Messaging（R648 选项）与控制器上的 KAREL 服务端程序通信，实现远程控制。",
  "solution": "使用 fanucpy 开源库（pip install fanucpy），配合控制器端的 MAPPDK 驱动（KAREL+TP 程序），通过 socket 协议实现 Python→FANUC 的全功能控制。",
  "verification": "1. pip install fanucpy 成功；2. 控制器端 MAPPDK 服务运行且端口 18735 可达；3. robot.connect() 返回成功；4. robot.get_curpos() 能返回当前位姿。"
}

## FANUC Robot Python Control via fanucpy Library

### 问题描述

需要从 Python 端控制 FANUC 工业机器人，包括关节运动、笛卡尔运动、夹爪控制、IO 读写、状态查询等操作。FANUC 控制器原生只支持 KAREL 和 TP 语言，没有 Python 接口。

### 根因分析

FANUC 控制器（如 R-30iB Mate Plus）运行专有的 KAREL/TP 语言环境，无法直接执行 Python 代码。解决方案是利用控制器的 **User Socket Messaging**（R648 选件）功能：

- 控制器端：运行 KAREL 编写的 socket 服务端程序（MAPPDK server），监听 TCP 端口
- Python 端：通过 TCP socket 发送结构化指令，接收执行结果
- 通信协议：基于 socket messaging 的请求-响应模式

### 修复方法/技术要点

#### 1. 环境准备

**控制器端选件要求：**
- R632 — KAREL
- R648 — User Socket Messaging

检查方法：MENU → NEXT → STATUS → Version ID → ORDER FI，确认列表中有 R632 和 R648。

**Python 端安装：**
```bash
pip install -U fanucpy
```

#### 2. 连接配置

```python
from fanucpy import Robot

robot = Robot(
    robot_model="Fanuc",
    host="192.168.1.100",  # 控制器 IP
    port=18735,            # MAPPDK 默认端口
    ee_DO_type="RDO",      # 末端执行器 DO 类型
    ee_DO_num=7,           # 末端执行器 DO 编号
)
robot.connect()
```

#### 3. 运动控制

```python
# 关节空间运动（6 轴角度值）
robot.move(
    "joint",
    vals=[19.0, 66.0, -33.0, 18.0, -30.0, -33.0],
    velocity=100,
    acceleration=100,
    cnt_val=0,       # 连续运动值（0=精确定位）
    linear=False
)

# 笛卡尔空间运动（XYZWPR 位姿值）
robot.move(
    "pose",
    vals=[0.0, -28.0, -35.0, 0.0, -55.0, 0.0],
    velocity=50,
    acceleration=50,
    cnt_val=0,
    linear=False
)
```

#### 4. 夹爪与 IO 控制

```python
# 夹爪
robot.gripper(True)   # 打开
robot.gripper(False)  # 关闭

# RDO（Robot Digital Output）
robot.get_rdo(rdo_num=7)
robot.set_rdo(rdo_num=7, value=True)

# DOUT（Digital Output）
robot.get_dout(dout_num=1)
robot.set_dout(dout_num=1, value=True)
```

#### 5. 状态查询

```python
print(f"当前位姿: {robot.get_curpos()}")
print(f"当前关节角: {robot.get_curjpos()}")
print(f"瞬时功率: {robot.get_ins_power()}")
print(f"夹爪状态: {robot.get_rdo(7)}")
```

#### 6. 调用外部程序

```python
robot.call_prog(prog_name)
```

#### 7. 控制器端网络配置

| 设置项 | 值 |
|--------|-----|
| 机器人 IP | 192.168.234.2（同网段） |
| 子网掩码 | 255.255.255.0 |
| DHCP | 禁用 |
| MAPPDK Server Tag | S8 |
| Server 端口 | 18735 |
| Server 协议 | SM (Socket Messaging) |
| Logger Tag | S7，端口 18736 |

控制器端需要运行 MAPPDK 主程序（mappdk.ls），它同时启动 server 和 logger。

#### 8. 保留资源

| 资源 | 用途 |
|------|------|
| USER FRAME=8, TOOL FRAME=8 | MAPPDK 专用 |
| R[81], R[82], R[83] | 速度、加速度、连续值 |
| PR[81] | 位置/关节值 |

### 验证方式

1. `pip install fanucpy` 安装无报错
2. 控制器端 MAPPDK 服务已在 S8 端口 18735 启动（SHOW → Servers → S8 → Current State: STARTED）
3. Python 执行 `robot.connect()` 返回成功
4. `robot.get_curpos()` 返回有效的 6 轴位姿数据
5. `robot.move("joint", ...)` 机器人实际运动到目标位置

### 来源

- GitHub: torayeff/fanucpy — Python package for FANUC industrial robots
- MAPPDK Driver 文档：github.com/torayeff/fanucpy/blob/main/fanuc.md
- 学术引用：Torayev et al., "Towards Modular and Plug-and-Produce Manufacturing Apps", Procedia CIRP, 2022
