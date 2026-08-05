{"id":"fanuc-karel-http-api-webcontrol","title":"FANUC KAREL HTTP API — WebControl Robot Motion and Monitoring","domain":"fanuc","subdomain":"karel-webcontrol","source":"github-fanuc-webcontrol-api.md","status":"draft","confidence":0.75,"created":"2026-07-12","tags":["fanuc","karel","http","api","webcontrol","rest","motion","monitoring"],"quality_score":75,"problem":"需要通过HTTP接口远程控制FANUC机器人运动、监控状态、管理程序执行，但FANUC原生不提供REST API","root_cause":"FANUC控制器内置KAREL webserver，但官方文档分散，缺少完整的API参考和使用示例","solution":"基于KAREL webserver实现HTTP API：webcontrol端点发送6种运动模式(关节/笛卡尔×绝对/相对)、webmonitor返回完整状态JSON(关节/笛卡尔/限位/状态/错误)、weblimit设置18个运动限位、webstart运行TP程序、webabort紧急停止","verification":"webcontrol/weblimit成功返回204状态码；webmonitor返回完整JSON包含joint/pose/limit/status/message/error/timestamp字段；各KAREL程序(webabort/webcheck/webkeep/webreset等)功能独立可测"}

### 问题描述

需要通过HTTP接口远程控制FANUC机器人：
- 发送运动指令(绝对/相对，关节/笛卡尔)
- 实时监控机器人状态(关节角、笛卡尔位置、限位、错误)
- 设置运动限位保护
- 管理程序执行(启动、停止、重置)

FANUC控制器内置KAREL webserver，但缺少完整的API文档。

### 根因分析

FANUC控制器支持KAREL程序作为webserver端点，但：
- 官方文档分散在不同手册中
- 缺少端到端的使用示例
- 各端点的参数格式和返回值需要逐一确认

### 修复方法/技术要点

#### 1. 运动控制端点 — webcontrol

**URL：** `/KAREL/webcontrol`

**方法：** GET

**参数：**
- `mtn_mod`：运动模式(1-6)
- `coord1`~`coord6`：6个坐标值(关节角或笛卡尔坐标)

**运动模式：**

| mtn_mod | 描述 |
|---------|------|
| 1 | 绝对运动，关节空间，关节插补 |
| 2 | 相对运动，关节空间，关节插补 |
| 3 | 绝对运动，笛卡尔空间，直线插补 |
| 4 | 绝对运动，笛卡尔空间，关节插补 |
| 5 | 相对运动，笛卡尔空间，直线插补 |
| 6 | 相对运动，笛卡尔空间，关节插补 |

**返回：** 204状态码(无内容)

**使用示例：**
```
GET /KAREL/webcontrol?str_mtn_mod=3&str_coord1=100&str_coord2=200&str_coord3=300&str_coord4=0&str_coord5=0&str_coord6=0
```
→ 绝对笛卡尔直线运动到(100, 200, 300, 0, 0, 0)

#### 2. 状态监控端点 — webmonitor

**URL：** `/KAREL/webmonitor`

**方法：** GET

**返回JSON结构：**
```json
{
  "robotid": ["控制器ID"],
  "joint": [J1, J2, J3, J4, J5, J6],
  "pose": [X, Y, Z, W, P, R],
  "limit": [xMax, yMax, zMax, xMin, yMin, zMin, j1Max, j2Max, j3Max, j4Max, j5Max, j6Max, j1Min, j2Min, j3Min, j4Min, j5Min, j6Min],
  "status": [task_running, webmotion_running],
  "message": [reachable, x_limit, y_limit, z_limit, j1_limit, j2_limit, j3_limit, j4_limit, j5_limit, j6_limit],
  "timestamp": ["当前时间"],
  "error": [error_code, "error_string"]
}
```

**字段说明：**
- `robotid`：从`$FNO`获取的控制器ID
- `joint`：当前关节角(J1-J6，REAL)
- `pose`：当前笛卡尔位置(X,Y,Z,W,P,R，REAL)
- `limit`：18个运动限位值
- `status[0]`：任务运行中(0/1)
- `status[1]`：webmotion运行中(0/1)
- `message[0]`：位置可达(0/1)
- `message[1-3]`：XYZ限位触发(0=正常, 3=正限位, 6=负限位)
- `message[4-9]`：J1-J6限位触发
- `error`：错误码和错误字符串

#### 3. 限位设置端点 — weblimit

**URL：** `/KAREL/weblimit`

**方法：** GET

**参数：**
- `limit_id`：限位ID(1-6, 11-16, 21-26)
- `limit_vl`：限位值(REAL)

**限位ID映射：**

| limit_id | 描述 | limit_id | 描述 | limit_id | 描述 |
|----------|------|----------|------|----------|------|
| 1 | x max | 11 | j1 max | 21 | j1 min |
| 2 | y max | 12 | j2 max | 22 | j2 min |
| 3 | z max | 13 | j3 max | 23 | j3 min |
| 4 | x min | 14 | j4 max | 24 | j4 min |
| 5 | y min | 15 | j5 max | 25 | j5 min |
| 6 | z min | 16 | j6 max | 26 | j6 min |

**返回：** 204状态码

#### 4. 程序管理端点

**启动TP程序：**
```
GET /KAREL/webstart?str_task=webmotion
```
- `task`：TP程序名(默认`webmotion`)

**其他KAREL程序：**

| 程序 | 功能 |
|------|------|
| `webabort` | 紧急停止：中止所有任务，保存当前位置到PR[40](关节)/PR[41](笛卡尔)，清除标志1-8，设置R[42]=999 |
| `webcheck` | 检查位置可达性、限位、安全寄存器值 |
| `webkeep` | 重置安全运动寄存器值 |
| `webreset` | 重置控制器并中止所有任务 |
| `webstop` | 停止webmotion程序 |
| `webprogram` | 获取控制器上的程序列表 |

#### 5. 典型使用流程

```
1. GET /KAREL/weblimit?str_limit_id=1&str_limit_vl=500   -- 设置X正限位
2. GET /KAREL/webstart?str_task=webmotion                  -- 启动运动任务
3. GET /KAREL/webmonitor                                   -- 监控状态
4. GET /KAREL/webcontrol?str_mtn_mod=3&str_coord1=...     -- 发送运动指令
5. GET /KAREL/webmonitor                                   -- 确认到达
6. GET /KAREL/webabort                                     -- 紧急停止(如需要)
```

### 验证方式

1. **运动控制**：发送webcontrol请求，验证返回204
2. **状态监控**：调用webmonitor，验证返回完整JSON(含joint/pose/limit/status/message/error/timestamp)
3. **限位设置**：设置限位后，尝试超限运动，验证被阻止
4. **程序管理**：通过webstart启动程序，通过webstop停止，通过webabort紧急停止
5. **安全验证**：测试webabort是否正确保存位置、清除标志、设置安全寄存器

### 来源

- FANUC KAREL WebControl API文档
- 基于KAREL webserver实现
- 默认端点：webcontrol, webmonitor, weblimit, webstart, webabort, webcheck, webkeep, webreset, webstop, webprogram