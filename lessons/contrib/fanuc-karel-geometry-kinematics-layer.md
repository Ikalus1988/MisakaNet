{"id":"fanuc-karel-geometry-kinematics-layer","title":"Geometry and Kinematics Layer — Shapes, Pose, Sensors for Robot Programming","domain":"fanuc","subdomain":"karel-geometry","source":"github-ka-boost-layer6-geometry-kinematics.md","status":"draft","confidence":0.8,"created":"2026-07-12","tags":["fanuc","karel","geometry","shapes","sensors","tof","plane","collision"],"quality_score":80,"problem":"KAREL原生缺少3D几何图元(平面、线段、圆柱、包围盒)的交集、投影、碰撞检测等操作，以及ToF传感器集成，限制了机器人在复杂几何环境中的编程能力","root_cause":"FANUC KAREL标准库仅提供基础数学函数，没有面向机器人应用的几何计算库和传感器抽象层","solution":"Ka-Boost Layer6提供三个模块：shapes模块实现3D几何图元(plane/line/segment/box/cylinder)及交集/投影/碰撞检测；pose模块提供运动学和坐标变换(详见pose专题)；sensors模块封装ToF激光测距传感器(支持Keyence IL300/IL065、Panasonic MLDS)，含校准、滑动窗口平均、边沿检测","verification":"shapes模块通过TP交互式示教程序验证(如shp_splitedv、incylinder)；sensors模块通过实际传感器标定和空间扫描验证"}

### 问题描述

FANUC KAREL标准库缺少面向机器人应用的3D几何计算能力：
- 没有平面、线段、圆柱等几何图元的定义和操作
- 缺少几何图元之间的交集、投影、距离计算
- 没有碰撞检测(点是否在包围盒/圆柱内)
- 缺少ToF激光测距传感器的统一抽象层

这些能力是机器人空间感知、路径规划、工件检测的基础。

### 根因分析

KAREL作为工业机器人编程语言，设计重点在任务控制和运动指令，而非几何计算。开发者需要自行实现：
- 3D空间中的平面方程、线段参数化
- 点到平面的距离/投影
- 两个平面的交线
- 包围盒/圆柱的碰撞检测
- 传感器数据的校准和滤波

### 修复方法/技术要点

#### 1. shapes模块 — 3D几何图元

**数据类型：**

```karel
t_LINE     { point: VECTOR; vec: VECTOR }       -- 参数化直线: p = point + vec*t
t_SEGMENT  { r0, r1: VECTOR }                   -- 线段: p = (1-t)*r0 + t*r1
t_PLANE    { normal: VECTOR; d: REAL; origin: VECTOR }  -- 平面方程: normal·xyz + d = 0
t_BOX      { verts[5], vects[3], normals[3]; centroid: VECTOR }
t_CYLINDER { origin: XYZWPR; radius, height: REAL }
```

**平面操作：**

```karel
-- 构造平面
shapes__create_plane(origin, normal_vec) : t_PLANE
shapes__create_plane_from_points(p1, p2, p3) : t_PLANE

-- 平面交集
shapes__plane_intersection_line(pl1, pl2) : t_LINE     -- 两平面交线
shapes__plane_intersection_bicsector(pl1, pl2) : VECTOR -- 两平面角平分面法线

-- 点到平面
shapes__project_point_on_plane(point, plane) : VECTOR   -- 投影点
shapes__distance_of_point_to_plane(point, plane) : REAL -- 距离
```

**6点几何(两平面各3点)：**

```karel
shapes__vector_from_2planes(p1..p6) : VECTOR          -- 两平面法线的叉积
shapes__euler_from_2planes(p1..p6) : VECTOR           -- 返回WPR欧拉角
shapes__bisector_from_2planes(p1..p6) : VECTOR        -- 角平分面法线
shapes__bisector_from_2planes_euler(p1..p6) : VECTOR  -- 角平分面欧拉角
```

**碰撞检测：**

```karel
box.point_collision(p) : BOOLEAN      -- 点是否在包围盒内
cylinder.point_collision(p) : BOOLEAN -- 点是否在圆柱内
```

**TP交互式程序：**
- `shp_splitedv`：分割设备
- `shp_bisecv`：角平分面向量
- `incylinder`：圆柱内碰撞检测

#### 2. sensors模块 — ToF传感器集成

**支持的传感器：**

| 传感器 | 量程 | 采样时间 | 输入 |
|--------|------|----------|------|
| Keyence IL300 | 280mm | 30ms | AI2, ±5V |
| Keyence IL065 | 50ms | 10ms | AI2, ±5V |
| Panasonic MLDS | — | — | 配置文件 |

**tof_sensor类API：**

```karel
-- 创建/销毁
new / delete

-- 配置
set_measurement_type(meas_type)    -- 单次或平均
set_sample_time(smpl_tme)
set_sim_analog(meas_mm)            -- 仿真模式

-- 读取
read_measurement() : REAL          -- 单次读数
read_range() : REAL                -- 滑动窗口平均
read_signal() : BOOLEAN            -- 信号检测
read_zero() : BOOLEAN              -- 零点检测

-- 边沿检测
watch_rising_edge() : BOOLEAN
watch_falling_edge() : BOOLEAN
watch_change() : BOOLEAN
```

**scan_part类 — 空间扫描：**

```karel
new / init(crd_sys, crd_axs, orientation)
set_orientation / set_coord_sys / set_scan_finished
```

**标定方法：** 线性回归(斜率-截距)。信号/零点检测：虚拟(计算)或物理DI引脚。

### 验证方式

1. **shapes模块**：通过TP交互式示教程序验证几何操作正确性
2. **碰撞检测**：使用已知几何形状验证box/cylinder的点碰撞检测
3. **传感器**：通过实际传感器标定和空间扫描验证读数精度
4. **集成测试**：在机器人上运行完整的ToF空间扫描流程

### 来源

- Ka-Boost项目 Layer6模块
- 模块：`lib/shapes`(3D几何)、`lib/pose`(运动学，详见专题)、`lib/sensors`(ToF传感器)
- 传感器驱动：`lib/sensors/tof/`子模块