## MisakaNet — 节点技能反馈通信模块

**MisakaNet 是通信子模块（前身为 Agent-Medici 通信层，现为独立项目）。**  
节点通过 GitHub Issues 上报 skill 使用反馈，Hub 消费后更新 Knowledge Graph。

### 目录结构

```
misakanet/
├── .github/ISSUE_TEMPLATE/feedback.yml  # Issue 模板（结构化上报）
├── schema/
│   ├── feedback.schema.json             # 反馈数据 JSON Schema
│   └── response.schema.json             # Hub 回复 JSON Schema
└── scripts/
    ├── feedback_report.py               # 节点侧：收集 + 上报反馈
    └── hub_poller.py                    # Hub 侧：消费反馈 + 更新图谱
```

### 消息生命周期

```
节点 (hp WSL)                     GitHub Issues               Hub (Windows)
     │                                │                           │
     │── POST /issues (feedback) ───→ │                           │
     │  labels: feedback,unprocessed  │                           │
     │                                │── GET /issues?labels= ──→│
     │                                │   feedback,unprocessed    │
     │                                │                           │── 解析 body
     │                                │                           │── 更新 KnowledgeGraph
     │                                │←── POST comment ────────│
     │                                │←── PATCH labels + close │
```

### 快速使用

**节点侧（WSL）：**
```bash
cd /path/to/MisakaNet
python misakanet/scripts/feedback_report.py
```

**Hub 侧（Windows）：**
```powershell
cd C:\Users\Eric Jia\MisakaNet
$env:MISAKANET_TOKEN = "ghp_..."
python misakanet\scripts\hub_poller.py
```

### 设计原则

- **节点是 Pull 方** — Hub 不下指令，只写建议到图谱
- **GitHub Issues = 消息通道** — Labels 做 topic 路由，无并发冲突
- **技能内容留在节点** — Hub 只存 embedding + meta + 图谱，不存完整 skill
