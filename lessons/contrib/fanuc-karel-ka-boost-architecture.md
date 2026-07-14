{
  "id": "fanuc-karel-ka-boost-architecture",
  "title": "Ka-Boost: 8-Layer KAREL Module Architecture and Build System",
  "domain": "fanuc",
  "subdomain": "karel-architecture",
  "source": "github.com/kobbled/ka-boost/CLAUDE.md",
  "status": "draft",
  "confidence": 0.85,
  "created": "2026-07-12",
  "tags": ["fanuc", "karel", "ka-boost", "architecture", "module-system", "rossum", "build-system", "gpp"],
  "quality_score": 85,
  "problem": "KAREL 语言缺乏标准库、泛型、关联数组、字符串操作等现代编程基础设施，大型项目（如 5 轴 DLP 3D 打印切片器）难以模块化开发和维护。",
  "root_cause": "KAREL 是类 Pascal 的编译语言，运行在 FANUC 控制器上，语言特性有限。Ka-Boost 通过 GPP 预处理器实现泛型、命名空间、OOP 类等高级特性，并建立 8 层模块依赖体系填补标准库空白。",
  "solution": "采用 Ka-Boost 的分层模块架构：从底层预处理器宏（Layer 0）到高层系统（Layer 7），每层只依赖下层。使用 rossum 包管理器 + ninja 构建系统管理依赖和编译。",
  "verification": "1. rossum 能解析 package.json 依赖图并生成 build.ninja；2. ninja 编译所有 .kl/.klc 文件生成 .pc 二进制；3. kpush 成功部署到控制器；4. 各层模块单元测试通过（KUnit HTTP 访问）。"
}

## Ka-Boost: 8-Layer KAREL Module Architecture and Build System

### 问题描述

KAREL 是 FANUC 机器人控制器上的类 Pascal 编译语言，缺乏泛型、关联数组、原生字符串操作、标准库等现代编程基础设施。开发大型项目（如 5 轴 DLP 3D 打印切片器）时，代码复用困难，模块化程度低，构建和部署流程复杂。

### 根因分析

KAREL 语言的先天限制：
- 无泛型支持 → 无法编写类型无关的容器（队列、哈希表等）
- 无标准库 → 字符串操作、数学运算、文件 I/O 都需从零实现
- 无命名空间 → 大型项目容易函数名冲突
- 无包管理 → 依赖关系手动管理
- 无 OOP → 无法封装状态和方法

Ka-Boost 通过工具链组合解决这些问题：
- **GPP 预处理器**：C 风格宏系统，实现泛型（`.klc` 类模板）和命名空间
- **rossum 包管理器**：解析 `package.json` 依赖图，生成 `build.ninja`
- **ninja 构建系统**：并行编译
- **kpush 部署工具**：FTP 推送 `.pc` 文件到控制器

### 修复方法/技术要点

#### 1. 工具链

| 工具 | 作用 |
|------|------|
| rossum | KAREL 包管理器，解析依赖，生成 build.ninja |
| ktransw | KAREL 转译器/预处理器（封装 GPP） |
| GPP | C 风格预处理器，实现泛型（.klc 类文件，.m 宏文件） |
| TP-Plus | 高级 DSL，编译为 FANUC TP (.ls) 程序 |
| ninja | 构建系统 |
| kpush | FTP 部署 .pc 到控制器 |

#### 2. 文件扩展名约定

| 扩展名 | 含义 |
|--------|------|
| `.kl` | KAREL 源文件 |
| `.klc` | KAREL 类模板（GPP 展开） |
| `.klt` | 类型/常量定义 |
| `.klh` | 头文件（函数声明） |
| `.m` | GPP 宏定义 |
| `.tpp` | TP-Plus 源文件 |
| `.ls` | FANUC TP 源文件（ASCII） |
| `.pc` | 编译后的 KAREL 二进制 |

#### 3. 8 层模块架构

每层只依赖下层，依赖关系自底向上：

| Layer | 模块 | 功能 |
|-------|------|------|
| 0 | ktransw-macros | GPP 宏 — 命名空间、泛型、头文件保护 |
| 1 | errors, system, Strings | 错误处理、系统类型、字符串操作 |
| 2 | math, matrix | 扩展数学、线性代数、4x4 变换矩阵 |
| 3 | hash, queue, iterator, graph | 容器和算法（KAREL 原生缺失） |
| 4 | files, csv, xmlib, socket | 文件 I/O、CSV、XML、TCP socket |
| 5 | registers, display, multitask, TPE, forms, KUnit | 寄存器 IO、TP 显示、并发、TP 程序、测试 |
| 6 | shapes, pose, sensors | 3D 几何、XYZWPR 运动学、ToF 传感器 |
| 7 | draw, layout, paths | 2D 切片器、文件缓冲、UV→XYZWPR 全流水线 |

#### 4. 依赖图

```
ktransw-macros
    └── errors, system, Strings, math
            └── matrix, hash, queue, iterator
                    └── files, csv, xmlib, socket
                            └── registers, display, multitask
                                    └── shapes, pose, sensors
                                            └── draw, graph, layout
                                                    └── paths
```

#### 5. 关键架构模式

**泛型（GPP 宏）：**
```
%define class_name myqueue
%include default_queue.klt     -- 定义 QUEUE_INDEX_TYPE, QUEUETYPE 等
%class myqueue(queue.klc)      -- 展开类模板
```

**命名空间：** 所有公开函数遵循 `modulename__routine` 命名（双下划线），由 `funcname`/`classfunc` 宏自动生成。

**OOP 类（.klc）：** 对象状态存储在 KAREL PATH 结构或全局变量中，方法通过 `declare_member` 宏绑定到类实例。

#### 6. 构建流程

```shell
cd lib/<module_name>
del /f robot.ini && setrobot    # 配置目标机器人/ROBOGUIDE
mkdir build && cd build
rossum .. -w -o                 # 解析依赖 + 生成 build.ninja
ninja                           # 编译
kpush                           # 部署到控制器
```

常用选项：
- `-t`：包含测试程序
- `-b`：构建所有依赖

#### 7. 控制器清理

```shell
kpush --delete                          # 删除 build 目录下所有程序
cd scripts && ./master_del.bat          # 删除所有 Ka-Boost 程序
cd scripts && ./master_test_del.bat     # 删除所有测试程序
```

**注意：** `draw` 和 `paths` 之间的交叉依赖可能导致 `MEMO-128 parameters are different` 错误。重新部署前应先运行 `master_del.bat` + `master_test_del.bat` 清理。

#### 8. 仓库结构

```
Ka-Boost/
├── lib/                 # 所有库子模块（每个是独立 git repo）
├── docs/                # 生成的 HTML 文档
├── scripts/             # Windows 批处理脚本
├── .claude/rules/       # 各层模块详细文档
└── readme.md
```

每个 `lib/` 子模块包含 `package.json`（rossum 清单），定义 `name`、`version`、`depends`（其他 Ka-Boost 包）和可选的 `tp-interfaces`（暴露给 TP 程序的函数）。

### 验证方式

1. `rossum .. -w -o` 成功生成 `build.ninja`，无依赖解析错误
2. `ninja` 编译所有源文件无错误，生成 `.pc` 二进制
3. `kpush` 成功将 `.pc` 文件推送到控制器
4. 各模块的 KUnit 测试在 `http://robot_ip/KAREL/test_name` 通过
5. 无 `MEMO-128` 参数冲突错误（清理后重新部署）

### 来源

- GitHub: kobbled/ka-boost — CLAUDE.md 项目架构文档
- 相关工具：rossum (包管理)、ktransw (转译器)、GPP (预处理器)、TP-Plus (DSL)
