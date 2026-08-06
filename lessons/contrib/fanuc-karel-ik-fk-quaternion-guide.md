{"id":"fanuc-karel-ik-fk-quaternion-guide","title":"IK/FK and Quaternion Math Guide for FANUC KAREL Robot Programming","domain":"fanuc","subdomain":"karel-kinematics","source":"github-ka-boost-kl-pose-readme.md","status":"draft","confidence":0.85,"created":"2026-07-12","tags":["fanuc","karel","ik","fk","quaternion","euler","pose","gimbal-lock","coordinate-system"],"quality_score":85,"problem":"FANUC KAREL机器人编程中，IK/FK求解、欧拉角处理、坐标系转换等操作容易出错，尤其是万向锁问题、z_axis参数误用、PR模式不匹配等常见陷阱","root_cause":"KAREL原生运动学函数有限，欧拉角在±90°俯仰角附近存在万向锁，坐标系约定(ZYX/RPY)容易混淆，PR寄存器有joint/Cartesian两种模式需要区分","solution":"pose库提供：solveIK/solveK做IK/FK(需检查get_ok)、vector_to_euler2用四元数避免万向锁、cylindrical_to_cartesian支持Z_AXES/VERT_AXES等z_axis参数、mask_posreg_xyz/orient做选择性PR更新、correctFrame用四元数对齐工具坐标系","verification":"KUnit测试套件覆盖IK/FK往返精度、四元数运算正确性、圆柱坐标转换精度；6种常见模式(路径规划IK、圆柱映射、表面法线对齐、切线转欧拉、选择性PR更新、4x4矩阵组合)均有完整代码示例"}

### 问题描述

FANUC KAREL机器人编程中，运动学和坐标变换操作容易出现以下问题：
- IK求解在奇异点附近失败，但程序不报错
- 欧拉角在±90°俯仰角附近出现万向锁，导致WPR值跳变
- 圆柱坐标转换的z_axis参数(Z_AXES vs VERT_AXES)选错，导致位置偏移
- PR寄存器有joint和Cartesian两种模式，读错模式会返回垃圾数据
- `quaternion__quat_to_pose`只返回WPR，调用者期望得到完整XYZWPR

### 根因分析

1. **万向锁**：欧拉角(ZYX/RPY)在俯仰角±90°时失去一个自由度，W和R轴耦合，导致WPR值不连续
2. **z_axis混淆**：`Z_AXES=3`表示局部坐标系的Z轴为旋转轴，`VERT_AXES=4`表示世界竖直方向为旋转轴，两者含义不同
3. **PR模式**：FANUC PR寄存器可存储joint或Cartesian数据，用错读取函数会返回错误数据
4. **四元数返回值**：`quat_to_pose`只填充WPR部分，xyz为0，需要手动组合

### 修复方法/技术要点

#### 1. IK/FK求解

```karel
VAR
    target  : XYZWPR
    jpos    : JOINTPOS

BEGIN
    -- 步骤1：设置正确的坐标系
    pose__set_userframe(1, 1)               -- 激活用户坐标系1，组1
    -- 步骤2：读取目标位置
    target = pose__get_posreg_xyz(10, 1)    -- 从PR[10]读取
    -- 步骤3：IK求解
    jpos = pose__solveIK(target, 1)
    -- 步骤4：必须检查成功标志
    IF NOT pose__get_ok THEN
        karelError(INVALID_INDEX, 'IK failed', ER_ABORT)
    ENDIF
    -- 步骤5：存储结果
    pose__set_posreg_joint(jpos, 11, 1)
END
```

**关键点：**
- IK前必须设置正确的userframe和toolframe
- IK后必须检查`pose__get_ok()`
- 奇异点附近IK可能失败

#### 2. 圆柱坐标转换

```karel
VAR
    origin    : XYZWPR   -- 圆柱轴心坐标系(来自标定)
    cyl_pose  : XYZWPR   -- (theta_deg=x, z_mm=y, r_mm=z, w, p, r)
    cart_pose : XYZWPR

BEGIN
    origin = pose__get_posreg_xyz(1, 1)
    -- cyl_pose.x = 角度(度), .y = 高度, .z = 半径
    cart_pose = pose__cylindrical_to_cartesian(origin, cyl_pose, Z_AXES)
    -- Z_AXES: 圆柱绕Z轴旋转
    -- 结果在机器人世界坐标系中，可直接用于运动
END
```

**z_axis参数选择：**
- `Z_AXES=3`：局部坐标系的Z轴是旋转轴(最常用)
- `X_AXES=1`/`Y_AXES=2`：旋转轴倾斜时使用
- `VERT_AXES=4`：世界竖直方向为旋转轴

#### 3. 表面法线对齐(correctFrame)

```karel
VAR
    p1, p2 : XYZWPR

BEGIN
    p1 = pose__get_posreg_xyz(1, 1)  -- 操作示教的表面点1
    p2 = pose__get_posreg_xyz(2, 1)  -- 操作示教的表面点2
    pose__correctFrame(Z_AXES, p1, p2)
    -- 活动用户坐标系已更新；工具Z轴对齐到表面法线
END
```

**内部原理：** 用四元数计算当前工具轴与测量法线之间的最短旋转，无万向锁。

#### 4. 切线向量转欧拉角

```karel
VAR
    tangent : VECTOR
    wpr     : VECTOR
    pos     : VECTOR
    pose    : XYZWPR
    cfg     : CONFIG

BEGIN
    tangent = VEC(0.707, 0.707, 0.0)
    -- 使用vector_to_euler2(四元数内部实现)，不要用vector_to_euler
    wpr = pose__vector_to_euler2(tangent, Z_AXES)
    pos = VEC(100.0, 200.0, 300.0)
    cfg = pose__set_config('F U T, 0, 0, 0')
    pose = pose__vector_to_pose(pos, wpr, cfg)
END
```

#### 5. 选择性PR更新

```karel
BEGIN
    -- 只更新高度，不改变朝向或XY位置
    pose__mask_posreg_xyz(pos.x, pos.y, new_z, 5, 1)
    -- 只旋转工具，不改变尖端位置
    pose__mask_posreg_orient(new_w, new_p, new_r, 5, 1)
END
```

#### 6. 4x4矩阵组合变换

```karel
VAR
    tool_rot : t_matarr
    offset   : t_matarr
    combined : t_matarr
    result   : XYZWPR

BEGIN
    tool_rot = matpose__rotz(90.0)
    offset   = matpose__transl(0.0, 50.0, 0.0)
    combined = offset.mult(tool_rot)  -- 组合：先旋转后平移
    result   = matpose__mat_to_pose(combined)
END
```

#### 7. 常见陷阱速查表

| 陷阱 | 症状 | 修复 |
|------|------|------|
| 近±90°俯仰用`vector_to_euler` | WPR跳变，路径不连续 | 改用`vector_to_euler2` |
| 圆柱转换z_axis选错 | 位置角度/高度错误 | `Z_AXES=3`=局部Z，`VERT_AXES=4`=世界竖直 |
| IK后不检查`get_ok` | 静默返回错误关节角 | 始终检查，失败则abort |
| 用`get_posreg_xyz`读joint模式PR | 错误或垃圾数据 | 先查`get_posreg_rep(reg_no, grp_no)` |
| `quat_to_pose`期望完整XYZWPR | 得到(0,0,0)位置 | 只返回WPR；用`vector_to_pose`组合 |
| 部署前不清除`shapes.pc`/`draw.pc` | `MEMO-128 parameters are different` | 先运行`master_del.bat` |
| 4x4矩阵欧拉约定不匹配 | 旋转看起来转置 | FANUC用ZYX/RPY：W=yaw(Z), P=pitch(Y), R=roll(X) |

### 验证方式

1. **IK/FK往返测试**：对同一位置做IK→FK，验证精度
2. **四元数测试**：验证旋转组合的正确性
3. **圆柱转换测试**：已知圆柱参数，验证转换后的笛卡尔坐标
4. **KUnit测试套件**：`test/test_pose.kl`和`test/test_matpose.kl`
5. **6种常见模式**：路径规划IK、圆柱映射、表面法线对齐、切线转欧拉、选择性PR更新、4x4矩阵组合

### 来源

- Ka-Boost项目 `lib/pose` 模块
- README文档：pose库的完整API参考和使用模式
- 常见陷阱来自实际开发经验总结