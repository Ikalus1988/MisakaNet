{"id":"fanuc-karel-kl-pose-api-reference","title":"KAREL Pose Library API Reference — IK/FK, Quaternion, Matrix Transforms","domain":"fanuc","subdomain":"karel-kinematics","source":"github-ka-boost-kl-pose-CLAUDE.md","status":"draft","confidence":0.85,"created":"2026-07-12","tags":["fanuc","karel","pose","ik","fk","quaternion","matrix","coordinate-transform"],"quality_score":85,"problem":"FANUC KAREL lacks built-in高级运动学函数，如逆运动学、四元数旋转、圆柱坐标转换、4x4矩阵运算等，导致机器人路径规划和坐标变换开发困难","root_cause":"KAREL原生仅提供基础PR读写和简单的位姿操作，缺少IK/FK求解器、万向锁安全的旋转表示、以及多坐标系之间的转换工具","solution":"Ka-Boost pose库提供完整的运动学工具链：solveIK/solveK做IK/FK、quaternion子模块避免万向锁、matpose做4x4矩阵变换、cylindrical_to_cartesian做圆柱坐标转换、correctFrame用四元数对齐工具坐标系到工件表面","verification":"通过KUnit测试套件验证：test_pose.kl覆盖IK/FK往返、字符串构造、mask操作、圆柱转换、外接圆心；test_matpose.kl覆盖矩阵和四元数运算"}

### 问题描述

FANUC KAREL标准库仅提供基础的PR读写和简单位姿操作，缺少以下关键能力：
- 逆运动学(IK)和正运动学(FK)求解
- 四元数旋转(避免万向锁)
- 4x4齐次变换矩阵运算
- 圆柱/极坐标系与笛卡尔坐标系之间的转换
- 从表面法线向量构建工具坐标系

这些能力是路径规划、5轴打印、曲面加工等高级应用的基础。

### 根因分析

KAREL作为FANUC的高级编程语言，设计目标是任务控制而非运动学计算。原生函数仅支持：
- `SET_UFRAME`/`SET_UTOOL`设置坐标系
- 基础的PR寄存器读写
- 简单的位姿加减

但不包含IK求解器(`CALC_JPOS_DATA`等底层函数未开放)、旋转表示转换、以及多坐标系变换链。

### 修复方法/技术要点

#### 1. IK/FK求解

```karel
-- 逆运动学：笛卡尔→关节角
joint_pose = pose__solveIK(cart_pose, grp_no)
-- 正运动学：关节角→笛卡尔
cart_pose = pose__solveK(joint_pose, grp_no)
-- 必须检查成功标志
IF NOT pose__get_ok THEN ... ENDIF
```

底层调用FANUC的`CALC_JPOS_DATA`和`CALC_KINE_DATA`。

#### 2. 四元数运算(避免万向锁)

```karel
-- 欧拉角→四元数
q = quaternion__pose_to_quat(pose)
-- 四元数乘法(旋转组合)
q_result = quaternion__mult(q1, q2)
-- 四元数→欧拉角(仅WPR，xyz=0)
wpr = quaternion__quat_to_pose(q)
-- 完整位姿需组合：
pose = pose__vector_to_pose(pos_vec, wpr, config)
```

**关键：** 使用`pose__vector_to_euler2`(四元数内部实现)替代`pose__vector_to_euler`，避免±90°俯仰角附近的万向锁。

#### 3. 4x4矩阵操作

```karel
-- 基本变换矩阵
rot = matpose__rotz(45.0)         -- Z轴旋转45°
trans = matpose__transl(100, 0, 0) -- X方向平移100mm
-- 组合变换
combined = trans.mult(rot)         -- 先旋转后平移
-- 矩阵↔位姿转换
matpose__pose_to_mat(pose, out_mat)
pose = matpose__mat_to_pose(mat)
```

矩阵格式(行主序)：
```
[R11 R12 R13  tx]
[R21 R22 R23  ty]
[R31 R32 R33  tz]
[0   0   0    1 ]
```

#### 4. 圆柱坐标转换

```karel
-- 圆柱(θ,z,r)→笛卡尔
cart = pose__cylindrical_to_cartesian(origin, cyl_pose, Z_AXES)
-- z_axis参数：Z_AXES=3(局部Z为旋转轴), VERT_AXES=4(世界竖直)
-- 反向转换
cyl = pose__cartesian_to_cylindrical(origin, cart_pose, Z_AXES, radius, TRUE)
```

#### 5. 表面法线对齐(correctFrame)

```karel
-- 操作示教两个表面点，对齐工具Z轴到表面法线
pose__correctFrame(Z_AXES, p1, p2)
-- 内部用四元数找最短旋转，无万向锁
```

#### 6. PR寄存器操作

```karel
-- 选择性更新：只改XYZ，保持WPR不变
pose__mask_posreg_xyz(x, y, z, reg_no, grp_no)
-- 只改朝向，保持位置不变
pose__mask_posreg_orient(w, p, r, reg_no, grp_no)
```

#### 7. 常见类型

| 类型 | 用途 |
|------|------|
| `T_CIRCLE` | 圆心+半径，由`find_circumcenter`返回 |
| `t_AXES_FRAME` | 工具坐标系三轴(orient/approach/normal) |
| `T_QUAT` | 四元数(w,x,y,z) |
| `t_matarr` | 4x4实数矩阵 |
| `t_rotarr` | 3x3旋转矩阵 |

#### 8. 常量

```karel
MAX_AXS = 9       -- 最大关节数
MAX_GRPS = 5      -- 最大机器人组数
X_AXES = 1        -- X轴参考
Y_AXES = 2        -- Y轴参考
Z_AXES = 3        -- Z轴参考
VERT_AXES = 4     -- 世界竖直轴
CC_POSITION = 1   -- PR类型：位置
CC_JOINT = 9      -- PR类型：关节
```

### 验证方式

1. **单元测试**：运行`test_pose.kl`和`test_matpose.kl`(通过KUnit HTTP接口：`http://robot.ip/KAREL/kunit?filenames=test_pose`)
2. **IK/FK往返测试**：对同一位置做IK→FK，验证精度在可接受范围内
3. **圆柱转换测试**：已知圆柱参数，验证转换后的笛卡尔坐标
4. **四元数测试**：验证旋转组合的正确性和万向锁避免

### 来源

- Ka-Boost项目 `lib/pose` 模块
- 文件：`pose.kl`(约1400行)、`matpose.kl`、`quaternion.kl`、`posetp.kl`
- 测试套件：`test/test_pose.kl`、`test/test_matpose.kl`