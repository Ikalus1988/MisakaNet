{
  "id": "fanuc-karel-core-utility-modules",
  "title": "KAREL Core Utility Modules: errors, system, Strings API Reference",
  "domain": "fanuc",
  "subdomain": "karel-programming",
  "source": "github.com/kobbled/ka-boost/.claude/rules/layer-1-core-utilities.md",
  "status": "draft",
  "confidence": 0.85,
  "created": "2026-07-12",
  "tags": ["fanuc", "karel", "ka-boost", "errors", "strings", "system", "utility", "api"],
  "quality_score": 85,
  "problem": "KAREL 缺乏标准库，错误处理、字符串操作、系统类型定义等基础功能需要从零实现，代码复用率低。",
  "root_cause": "KAREL 语言没有标准库，连基本的字符串分割、类型转换、错误码管理都需要手动实现。Ka-Boost Layer 1 提供三个核心模块（errors, system, Strings）作为所有上层模块的基础。",
  "solution": "使用 Ka-Boost Layer 1 的三个基础模块：errors（错误处理+变量初始化）、system（系统类型+时间+坐标系）、Strings（字符串全操作），作为 KAREL 项目的基础设施。",
  "verification": "1. errors 模块：karelError 能输出到 TP 显示和历史记录；2. system 模块：system__date()/system__time() 返回正确格式；3. Strings 模块：split_str、i_to_s/r_to_s 等函数在 KUnit 测试中通过。"
}

## KAREL Core Utility Modules: errors, system, Strings API Reference

### 问题描述

KAREL 是 FANUC 控制器上的类 Pascal 编译语言，没有标准库。开发者在每个项目中都要重复实现错误处理、字符串操作、类型转换等基础功能，导致代码冗余且质量参差不齐。

### 根因分析

KAREL 语言的核心缺陷：
- 无错误码管理机制 → 每个项目自定义错误处理，不统一
- 无字符串操作函数 → 连 split、trim、类型转换都要手写
- 无统一的系统类型定义 → 数据类型和比较器散落各处
- 无时间/日期 API → 获取系统时间需要直接操作控制器接口

Ka-Boost Layer 1 的三个模块（errors, system, Strings）是所有上层模块的共同基础，形成 KAREL 项目的"标准库"。

### 修复方法/技术要点

#### 1. errors 模块 — 错误处理与变量初始化

**核心 API：**

```karel
-- 状态检查：非 SUCCESS 则中止
CHK_STAT(rec_stat : INTEGER)

-- 错误报告：errorType 0=警告, 1=警告+历史, 2=中止
karelError(stat : INTEGER; errStr : STRING; errorType : INTEGER)

-- 变量初始化（吞掉 error 12311）
SET_UNINIT_I(progname, varname)   -- INTEGER
SET_UNINIT_R(progname, varname)   -- REAL
SET_UNINIT_B(progname, varname)   -- BOOLEAN
SET_UNINIT_V(progname, varname)   -- VECTOR
SET_UNINIT_F(progname, varname)   -- FRAME
SET_UNINIT_S(progname, varname)   -- STRING

-- 数组范围初始化
SET_UNI_ARRS(progname, varname, start_i, stop_i)
```

**命名错误码（errors.klt）：**

| 类别 | 典型错误码 |
|------|-----------|
| 数组 | ARR_LEN_MISMATCH, INVALID_INDEX |
| 变量 | VAR_UNINIT |
| 文件 | FILE_NOT_OPEN |
| 程序 | TPE_PROGRAM_DOES_NOT_EXIST |
| 队列 | QUEUE_IS_EMPTY |
| 位置 | POS_TYPE_MISMATCH |
| 运动 | SEARCH_MOTION_FAILED |

**依赖：** Strings（用于 `str_parse` — 将长错误信息换行适配 TP 显示屏）。

#### 2. system 模块 — 系统接口与类型定义

**时间日期：**

```karel
system__date() : STRING    -- 返回 'DD-MMM-YYYY'
system__time() : STRING    -- 返回 'HH:MM:SS'
```

**Leader Frame（双臂机器人坐标系）：**

```karel
system__set_leader_frame(cd_pair_no, ldr_frm_no, frm)
system__get_leader_frame(cd_pair_no, ldr_frm_no) : XYZWPR
system__mask_leader_frame(cd_pair_no, ldr_frm_no, axs, val)
```

**工具函数：**

```karel
system__pns_to_str() : STRING      -- 输入引脚 → 程序名映射
system__int_to_bool(int) : BOOLEAN
system__tdata_glte(data1, data2, typ, comparator) : BOOLEAN  -- 通用比较
```

**向量构造：**

```karel
VEC(x, y, z) : VECTOR              -- 3D 向量
VEC2D(x, y) : VECTOR               -- 2D 向量（z=0）
compare_VEC(v1, v2, tolerance) : BOOLEAN  -- 容差比较
```

**重要类型（systemlib.datatypes.klt）：**

```karel
t_DATA_TYPE   -- 联合体：可存储 INT, REAL, STRING, BOOL, VEC, POSE, CONFIG
t_INTEGER, t_REAL, t_STRING16, t_BOOL, t_VECTOR, t_POSE  -- 原子类型包装
VECTOR2D, VECTOR2Di  -- 2D 向量类型
```

**系统变量宏（systemvars.klt）：**

| 宏 | 用途 |
|-----|------|
| ZEROPOS(g) | 零位姿 |
| ZEROARR | 零数组 |
| TOTAL_GROUPS | 运动组总数 |
| GROUP_KINEMATICS(g) | 运动学类型 |
| CURRENT_UTOOL | 当前工具坐标系 |
| CURRENT_UFRAME | 当前用户坐标系 |
| DYNAMIC_LEADER(f,l) | 动态 leader frame |

**常量（systemlib.codes.klt）：**

类型码：`C_INT`, `C_REAL`, `C_STR`, `C_BOOL`, `C_VEC`, `C_POS`, `C_POSEXT`, `C_CONFIG`
比较器：`C_GREATER`, `C_LESSER`, `C_EQUAL`, `C_GREATEREQL`, `C_LESSEREQL`

#### 3. Strings 模块 — 字符串全操作

KAREL 原生只有 STRING 类型赋值和简单拼接，Strings 模块补齐了所有常用操作。

**分割/解析：**

```karel
split_str(str, delim, out_arr[])          -- 按分隔符分割
extract_str(str, start_delim, stop_delim) : STRING  -- 提取子串
rev_split(str, delim, out_arr[])          -- 反向分割
char_index(str, chr) : INTEGER            -- 字符位置
takeStr(str, chr) : STRING                -- 分隔符前部分
takeNextStr(str, chr) : STRING            -- 分隔符后部分
search_str(str, sub) : INTEGER            -- 子串搜索
getIntInStr(str) : INTEGER                -- 提取字符串中的整数
```

**裁剪/格式化：**

```karel
lstrip(str) / rstrip(str)                 -- 去除首尾空格
lstripChar(str, chr) / rstripChar(str, chr) -- 去除指定字符
delim_strip(str, delim)                   -- 去除分隔符
to_upper(str) : STRING                    -- 转大写
str_parse(str, max_len, out_arr[])        -- 按最大行长换行（TP 显示用）
```

**路径工具：**

```karel
splitext(path) : STRING      -- 去扩展名的文件名
get_ext(path) : STRING       -- 获取扩展名
basename(path) : STRING      -- 文件名部分
get_device(path) : STRING    -- 设备名
get_progname(ref) : STRING   -- 从 '[progname]varname' 提取程序名
get_varname(ref) : STRING    -- 从 '[progname]varname' 提取变量名
```

**类型→字符串：**

```karel
i_to_s(i) : STRING                    -- 整数转字符串
r_to_s(r) : STRING                    -- 实数转字符串
b_to_s(b) : STRING                    -- 布尔转字符串
p_to_s(pose) : STRING                 -- 位姿转多行字符串
pose_to_s(pose, delim) : STRING       -- 位姿转分隔字符串
vec_to_s(v, delim) : STRING           -- 向量转字符串
joint_to_s(jpos, delim) : STRING      -- 关节角转字符串
rarr_to_s / iarr_to_s / sarr_to_s     -- 数组转字符串
i_to_byte(i) : STRING                 -- 整数转二进制字符串
```

**字符串→类型：**

```karel
s_to_i(str) : INTEGER
s_to_r(str) : REAL
s_to_b(str) : BOOLEAN
s_to_xyzwpr(str) : XYZWPR
s_to_vec(str) : VECTOR
s_to_joint(str) : JOINTPOS
s_to_config(str) : CONFIG
s_to_arr / s_to_rarr / s_to_iarr      -- 字符串转数组
bin_to_i(bin_str) : INTEGER           -- 二进制字符串转整数
```

**验证：**

```karel
charisnum(c) : BOOLEAN          -- 字符是否为数字
strisreal(str) : BOOLEAN        -- 字符串是否为实数
strisint(str) : BOOLEAN         -- 字符串是否为整数
delim_check(delim) : BOOLEAN    -- 分隔符是否有效
```

### 验证方式

1. **errors 模块：** 调用 `karelError(0, 'test error', 2)` 后 TP 显示屏显示错误信息，TP 历史记录中有对应条目
2. **system 模块：** `system__date()` 返回格式如 '12-JUL-2026'，`system__time()` 返回格式如 '14:30:00'
3. **Strings 模块：** `split_str('a,b,c', ',', arr)` 后 arr 包含 ['a', 'b', 'c']；`i_to_s(123)` 返回 '123'
4. 所有模块的 KUnit 测试通过

### 来源

- GitHub: kobbled/ka-boost — Layer 1 Core Utilities 文档 (.claude/rules/layer-1-core-utilities.md)
- 模块源码：lib/errors, lib/system, lib/Strings
