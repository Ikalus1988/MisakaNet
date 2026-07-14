{
  "id": "fanuc-karel-unit-testing-kunit",
  "title": "Unit Testing FANUC KAREL Programs with KUnit Framework",
  "domain": "fanuc",
  "subdomain": "karel-testing",
  "source": "github.com/kylerlippincott/kunit",
  "status": "draft",
  "confidence": 0.8,
  "created": "2026-07-12",
  "tags": ["fanuc", "karel", "unit-testing", "kunit", "roboguide", "quality"],
  "quality_score": 80,
  "problem": "FANUC KAREL 程序缺乏单元测试手段，无法在部署前验证逻辑正确性，调试依赖实机运行。",
  "root_cause": "KAREL 是类 Pascal 的编译语言，运行在 FANUC 控制器上，没有原生的测试框架。KUnit 通过 KAREL 程序实现测试运行器，利用控制器的 HTTP 服务提供 Web 浏览器访问的测试结果输出。",
  "solution": "使用 KUnit 框架编写 KAREL 单元测试：编写返回 BOOLEAN 的测试函数，通过 HTTP 端点运行测试并在浏览器查看结果。",
  "verification": "1. kunit.pc 和 strings.pc 已部署到控制器；2. 测试程序翻译编译成功；3. 浏览器访问 http://robot_ip/KAREL/kunit?filenames=test_name 显示测试结果；4. 所有断言通过，0 failures。"
}

## Unit Testing FANUC KAREL Programs with KUnit Framework

### 问题描述

FANUC KAREL 程序没有原生的单元测试支持。开发者通常需要将程序部署到控制器或 ROBOGUIDE 上运行才能验证逻辑，调试效率低且风险高。需要一种在部署前就能系统性验证 KAREL 程序逻辑的方法。

### 根因分析

KAREL 是 FANUC 专有的类 Pascal 编译语言，运行环境是机器人控制器，不支持标准的软件测试工具链。KUnit 框架通过以下机制解决这个问题：

- 测试用例是返回 `BOOLEAN` 的 KAREL ROUTINE（true=通过，false=失败）
- KUnit 提供断言函数（`kunit_eq_int`, `kunit_eq_str` 等）封装比较逻辑
- 测试运行器通过控制器的 HTTP 服务输出结果，可在浏览器中查看
- 支持并行运行多个测试文件

### 修复方法/技术要点

#### 1. 安装步骤

1. 下载 KUnit 发布包
2. 将 `kunit.pc` 和 `vendor/strings.pc` 复制到机器人控制器
3. 将 `kunit.h.kl` 放到项目的 support 目录或与测试文件同目录
4. 测试文件中 `%INCLUDE kunit.h`
5. 翻译并部署 KAREL 程序到控制器

#### 2. 编写测试用例

完整示例——测试一个整数加法函数：

```karel
PROGRAM test_add_int
%NOLOCKGROUP          -- 浏览器运行 KAREL 必须
%INCLUDE kunit.h

-- 被测函数
ROUTINE add_int(l : INTEGER; r : INTEGER) : INTEGER
BEGIN
  RETURN(l + r)
END add_int

-- 测试用例：每个返回 BOOLEAN
ROUTINE test_11 : BOOLEAN
BEGIN
  RETURN(kunit_eq_int(2, add_int(1,1)))
END test_11

ROUTINE test_22 : BOOLEAN
BEGIN
  RETURN(kunit_eq_int(4, add_int(2,2)))
END test_22

ROUTINE test_00 : BOOLEAN
BEGIN
  RETURN(kunit_eq_int(0, add_int(0,0)))
END test_00

BEGIN
  -- 注册并运行测试
  kunit_test('1+1=2', test_11)
  kunit_test('2+2=4', test_22)
  kunit_test('0+0=0', test_00)

  -- 必须调用，标记测试结束
  kunit_done
END test_add_int
```

**关键约定：**
- `%NOLOCKGROUP` 是必须的，否则浏览器无法运行 KAREL
- 测试 ROUTINE 返回 BOOLEAN：true=pass, false=fail
- 文件末尾必须调用 `kunit_done`
- 简单测试可直接内联：`kunit_test('1+1=2', kunit_eq_int(2, add_int(1,1)))`

#### 3. 可用断言一览

| 断言函数 | 用途 |
|----------|------|
| `kunit_assert(b : BOOLEAN)` | 断言条件为真 |
| `kunit_eq_int(expected, actual)` | 断言两个 INTEGER 相等 |
| `kunit_eq_r(expected, actual)` | 断言两个 REAL 相等 |
| `kunit_eq_str(expected, actual)` | 断言两个 STRING 相等 |
| `kunit_eq_pos(expected, actual)` | 断言两个 XYZWPR 位置相等 |
| `kunit_eq_pip(fname : STRING)` | 断言 pipe 内容与文件一致（超长字符串比较） |
| `kunit_un_int(actual)` | 断言 INTEGER 为 UNINIT |
| `kunit_un_str(actual)` | 断言 STRING 为 UNINIT |
| `kunit_un_r(actual)` | 断言 REAL 为 UNINIT |

#### 4. 运行测试

**单个测试文件：**
```
http://your.robot/KAREL/kunit?filenames=your_test
```

**多个测试文件（逗号分隔）：**
```
http://your.robot/KAREL/kunit?filenames=test_kunit,test_something_else
```

**HTML 格式输出：**
```
http://your.robot/KAREL/kunit?filenames=your_test&output=html
```

#### 5. 测试输出示例

```
KUnit v1.0.0
........
Finished in 0.002 seconds
4000.0 tests/sec, 9500.0 assertions/sec
8 tests, 19 assertions, 0 failures
```

**失败时的调试信息：**
```
1) Failure:
a eqls a
Expected "a" but got "b"
```

#### 6. 开发环境要求

- ROBOGUIDE 已安装
- WinOLPC bin 目录在系统 PATH 中
- GnuWin（Windows 环境）
- 构建：`make` 编译 KAREL 二进制 PC 文件
- 部署：复制到 ROBOGUIDE 或真实机器人
- 运行：`http://robot.ip/KAREL/test_kunit`

### 验证方式

1. `kunit.pc` 和 `strings.pc` 已正确部署到控制器
2. 测试程序翻译编译无错误
3. 浏览器访问 `http://robot_ip/KAREL/kunit?filenames=test_add_int` 显示测试结果
4. 输出包含 "0 failures"
5. 故意修改断言期望值，确认失败时有明确的 Expected/Actual 信息

### 来源

- GitHub: kylerlippincott/kunit — Simple unit testing framework for FANUC KAREL
- 适用于所有支持 KAREL 的 FANUC 控制器（需 R632 选件）
