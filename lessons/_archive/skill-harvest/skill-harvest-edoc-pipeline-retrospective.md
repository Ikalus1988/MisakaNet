---
domain: "archive"
title: "Edoc Pipeline Retrospective"
verification: "metadata-normalized"
source: "skill-pipeline"
status: "draft"
created: "2026-05-09"
---

## 背景

（此 lesson 从 skill `edoc-pipeline-retrospective` 自动提取，待补全）

## 根因

（待补充）

## 修复

# Edoc 建库调试教训记录

## 2026-04-16/17 全盘扫描 + 批量导入（10528 PDFs）

### 全盘扫描策略（经验教训）

**1. 扫描方式：find > os.walk（针对大目录/万级文件）**
- `os.walk` + Python 循环：300秒超时，对 F: 盘 19k PDFs 无法完成
- `find /mnt/f -name "*.pdf" -size +0`：后台运行，~1000条/秒，完整结果存文本文件
- 大目录优先用 find，Python 只需读结果文件

**2. 去重策略：文件名+大小 > MD5（针对万级文件）**
- MD5 计算 19k 文件前 1MB：超时（>300s）
- 文件名(小写) + 文件大小 指纹：<10秒完成
- 精确 MD5 只在最终合并候选时对少量文件使用

**3. 噪音过滤模式（快速排除非知识类 PDF）**
```python
noise_patterns = [
    'baldur','bg3','BG3','character sheet',  # 游戏
    'rabbit','荷兰鼠','tiger',               # 调查问卷
    'matplotlib','mpl-data','site-packages',  # Python库
    '生物医药','rarecare',                   # 无关行业
    'ragflow','test/benchmark',               # 测试数据
    'steamapps','common/',                   # 游戏目录
    '$recycle','system volume',              # 系统目录
    '企业微信','WXWork/Cache',               # 微信缓存
    'MsgAttach',                             # 邮件附件（合同/保单）
]
```

**4. 扫描结果必须持久化**
- 临时存 `/tmp/` 会在会话间丢失
- 正确做法：扫描结果存 `~/.hermes/scripts/edoc_scan_<drive>.json`
- 下次直接读文件跳过扫描

**5. 典型扫描结果分布（用户筛选偏好）**
| 目录 | 内容 | 判定 |
|------|------|------|
| project/ | 机器人/汽车工程文档 | ✅ |
| 调试资料/ | 西门子PLC/KUKA/OpenCV | ✅ |
| 软件/ | KUKA WorkVisual/ABB手册 | ✅ |
| 标准培训相关/ | 主机厂标准/培训手册 | ✅ |
| 观致办公/WXWork | 会议纪要/微信缓存 | ❌ |
| ikalus07/MsgAttach | 保单/合同/扫描件 | ❌ |

**6. 标准化导入流程**
```
1. find 扫描目标盘 → /tmp/pdfs.txt
2. Python 读文件 + 文件名/大小去重 + 噪音过滤
3. 展示目录分布 → 用户确认要哪些
4. 筛选后写入 edoc_ingest.py NEW_PDFS 列表（patch）
5. HF_HUB_OFFLINE=1 python3 edoc_ingest.py（后台）
6. 监控日志 + GPU显存，等完成通知
```

### 预估导入时间
- 小 PDF（<10页）：<5秒
- 中 PDF（100-400页）：5-30秒
- 大 PDF（500+页）：100-500秒（pymupdf 解析是瓶颈）
- 公式：总耗时 ≈ Σ(页数) × 0.85秒/页 + Σ(批次数) × 0.5秒

---

## 2026-04-16 第二次增量导入（6 PDFs，38,037 chunks）

### 实际导入结果
| PDF | 页数 | chunks | 耗时 |
|-----|------|--------|------|
| KAREL Reference 6.31 | 941 | 2303 | 803s |
| 系统变量表 | 503 | 1512 | 484s |
| FANUC License Server | 53 | 92 | 3s |
| Bosch Servo Gun | 6 | 11 | 5s |
| R-30iA FSSB Line Setting | 7 | 12 | 1s |
| 3rd Party Vision Sensor | 6 | 7 | 1s |

**总计：+3937 chunks in 1304s（约22分钟）。最终 38,037 chunks，148 个 source。**

### 启动命令
```bash
export HF_HUB_OFFLINE=1 && cd ~/.hermes && venv/bin/python3 scripts/edoc_ingest.py
```
`HF_HUB_OFFLINE=1` 防止 BGE 加载时 httpx 报 network unreachable。

### 多旧实例通知问题
watchdog 可能同时启动多个 edoc_ingest 实例，旧实例（20:07/20:13/20:17/20:21）被 SIGTERM 终止后仍会推送后台通知（ERROR, exit 143）。**判断标准**：只看 exit 0 且 collection count 跳升的那条。所有旧实例通知（exit 143, torch is not defined, network unreachable）一律可忽略。

### 旧实例常见错误速查
| 错误 | 原因 | 处理 |
|------|------|------|
| `torch.ConnectError: Network is unreachable` | 没设 `HF_HUB_OFFLINE=1` | 用正确命令重跑 |
| `NameError: name 'torch' is not defined` | torch import 缺失 | 脚本已修复，重跑即可 |
| `exit 143, tcsetattr` | SIGTERM 强制终止 | 无害，忽略 |
| 20:34 启动的那条 exit 0 | 真正成功的那次 | 看这条 |

---

## 2026-04-16 增量导入（edoc_ingest.py）

### 后台进程日志读取（关键！）
Python `print()` 在非 tty 环境下有缓冲，`tail -f` 可能读不到最新行。正确做法：
```python
with open('edoc_ingest.log') as f:
    f.seek(0, 2)          # 定位 EOF
    size = f.tell()
    f.seek(max(0, size-2000))  # 

## 验证

（待补充）
