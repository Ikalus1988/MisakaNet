{"id":"fanuc-karel-uv-to-xyzwpr-pipeline","title":"UV-to-XYZWPR Pipeline — From 2D Slice Geometry to Robot Motion","domain":"fanuc","subdomain":"karel-slicer","source":"github-ka-boost-layer7-high-level-systems.md","status":"draft","confidence":0.8,"created":"2026-07-12","tags":["fanuc","karel","path-planning","slicer","uv-to-xyzwpr","dxf","svg","5-axis"],"quality_score":80,"problem":"5轴DLP 3D打印切片器需要将2D切片几何(SVG/DXF)转换为机器人可执行的XYZWPR运动指令，中间涉及光栅化、路径规划、坐标系转换、多层迭代等复杂流程","root_cause":"切片器管线跨越多个模块(draw→pathplan→pathmake→pathmotion→pathlayer)，每个模块负责不同阶段的转换，缺乏统一的端到端参考文档","solution":"Ka-Boost Layer7实现完整的UV→XYZWPR管线：draw模块做2D光栅化和轮廓提取，pathplan用图算法排序路径段，pathmake做插值和坐标转换，pathmotion发TP运动指令，pathlayer做逐层迭代和硬件控制","verification":"通过实际5轴DLP打印验证管线完整性，Python工具链(DXF/SVG解析、Clipper裁剪、Matplotlib可视化)用于离线验证几何正确性"}

### 问题描述

5轴DLP 3D打印切片器需要将2D切片几何(从SVG/DXF文件导入)转换为机器人可执行的XYZWPR运动指令。整个流程涉及多个阶段：2D几何处理、路径规划排序、坐标系转换、运动插值、多层迭代、硬件控制。每个阶段需要不同的算法和数据结构。

### 根因分析

切片器管线跨越5个核心模块，每个模块负责不同阶段的转换：

```
[2D Slice Geometry] SVG/DXF导入
        ↓
    lib/draw → t_VEC_PATH (MOVETO/LINETO/CURVE3/CURVE4/CLOSE)
        ↓
    pathplan → 有序段索引 (MST/NN/raster排序)
        ↓
    pathmake → t_TOOLPATH (XYZWPR + 速度/点) + 坐标转换
        ↓
    pathmotion → TP运动指令 (MOVE_LINE/MOVE_CIRC)
        ↓
    pathlayer → 逐层迭代 + 硬件控制(激光/粉末)
```

### 修复方法/技术要点

#### 1. draw模块 — 2D几何处理

核心功能：将多边形几何转换为矢量路径。

**关键数据类型：**
- `t_VEC_PATH`：矢量路径节点(路径码 + 多边形ID)
- `t_RASTER`：光栅参数(角度、线宽、间距、方向)

**关键API：**
```karel
-- 光栅填充：用平行线填充多边形
draw__raster_lines(polygon, raster_params, out_lines[])
-- 轮廓提取
draw__trace(polygon, out_contours[])
-- 凸包
draw__convex_hull(points[], out[])
-- 包围盒
draw__bounding_box(points[]) : t_RECT
-- 多边形内缩/旋转/缩放
draw__inset_polygon(polygon, offset, out[])
draw__rotate_polygon(polygon, angle, out[])
-- 碰撞检测
draw__point_collision_polygon(p, polygon) : BOOLEAN
```

**OOP画布(canvas)：**
```karel
canvas__new/init/delete
canvas__append_polygon / append_vertex
canvas__raster(raster_params) / canvas__trace
canvas__rotate_canvas / scale_polygons / inset_polygons
```

**Python工具链：**
- `utils/dxf/`：DXF→CSV转换
- `utils/svg/`：SVG路径解析(svgpy)
- `utils/slices/`：Python Clipper多边形裁剪
- `viz/`：Matplotlib调试可视化

#### 2. pathplan模块 — 路径段排序

使用图算法确定路径段的最优遍历顺序。

```karel
new / init(coord_frame)
importPath / append_path
get_plan() : INTEGER[]          -- 排序后的段索引

-- 图算法
MST(start_node, out_pth)        -- 最小生成树遍历
NN_graph(k)                     -- k近邻图
raster_graph()                  -- 优化的光栅线排序
```

#### 3. pathmake模块 — 路径生成与插值

将规划好的路径段转换为密集的运动点云(含速度曲线)。

```karel
new / init(coord_frame, origin, path_planner)
makeline(start, end, spacing)
interpolate_toolpath(segment, spacing)  -- 线性 + 贝塞尔插值
set_segment_speed_bounds(start_spd, end_spd)
```

**路径码(兼容matplotlib)：**
- `PTH_MOVETO`：抬笔移动
- `PTH_LINETO`：直线
- `PTH_CURVE3`：二次贝塞尔
- `PTH_CURVE4`：三次贝塞尔
- `PTH_CLOSE`：闭合路径

**坐标系统：**
- `PTH_CARTESIAN`：笛卡尔
- `PTH_CYLINDER`：圆柱
- `PTH_POLAR`：极坐标

**光栅类型：**
- `ONEWAY`：单向
- `ZIGZAG`：锯齿形
- `NEARESTNEIGHBOR`：最近邻
- `BOTTOMFILL`/`CASCADEFILL`：填充策略

#### 4. pathmotion模块 — 运动执行

向机器人发送实际TP运动指令。支持可插拔接口(6轴机器人、旋转台、变位机)。

```karel
-- 运动基类
set_tool_offset / set_speeds / set_interpolation
set_coord_frame / set_idod

-- 机器人运动(继承motion)
move / moveLine / moveArc / movePos
movePoly / movePolyFull / movePolyArc
run_approach_path / run_retract_path
moveApproach / moveRetract
```

接口模板`motion.interface.klt`支持在不同运动后端之间切换，无需修改调用代码。

#### 5. pathlayer模块 — 逐层迭代

协调多层打印：迭代Z层和通道，控制激光/粉末硬件，管理布局文件加载。

```karel
new / init(layer_params, pass_params)
next_layer / next_pass
import_layout / open_layout / close_layout
set_drawing_type(typ)     -- LINES, CONTOURS, RASTER等
lam_start / lam_stop      -- 激光/粉末硬件控制钩子
```

#### 6. 布局模块(layout)

通用模板化缓冲文件读取器，将结构化CSV(或G-code)切片输出反序列化为KAREL PATH缓冲区。

```karel
loadBuffer() : BOOLEAN        -- 加载下一个缓冲区；TRUE=还有数据
bufferLength() : INTEGER
```

缓冲策略：
- `pathlayer_by_layer.klt`：每个Z层一个缓冲区
- `pathlayer_by_pass.klt`：每层内每个通道一个缓冲区

#### 7. 激光/粉末参数(lam子包)

```karel
t_LASER     { power: REAL }
t_POWDER    { wps_no, rpm, lpm, flow_rate, height: REAL; powder_type: INTEGER }
t_HOPPERS   { hopper1, hopper2: t_POWDER }
t_DEPTHREGR { a, b, c: REAL }  -- 二次多项式：a*x^2 + b*x + c，用于Z高度补偿
```

### 验证方式

1. **几何验证**：使用Python工具链(DXF/SVG解析 + Clipper裁剪 + Matplotlib可视化)离线验证2D几何正确性
2. **路径验证**：验证光栅填充、轮廓提取、路径排序的输出
3. **运动验证**：在实际机器人上验证pathmotion发出的运动指令
4. **端到端验证**：完成一次完整的5轴DLP打印，验证管线完整性

### 来源

- Ka-Boost项目 Layer7模块
- 模块：`lib/draw`(光栅化)、`lib/paths`(路径系统，含pathlib/pathplan/pathmake/pathmotion/pathlayer)
- 辅助工具：Python DXF/SVG/Clipper工具链