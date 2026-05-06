#!/usr/bin/env python3
"""
MisakaNet Hub Poller (Hub 侧)
====================================================
从 GitHub Issues 消费节点上报的反馈，直接更新 Hub 的 Knowledge Graph。

部署: agent-medici/misakanet/scripts/hub_poller.py
运行: cd /path/to/agent-medici && python misakanet/scripts/hub_poller.py

依赖:
  pip install requests pyyaml
  环境变量: MISAKANET_TOKEN 或 GITHUB_TOKEN
"""

import json
import os
import sys
import yaml
from datetime import datetime, timezone

# 项目根目录 (agent-medici/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

REPO = os.environ.get("MISAKANET_REPO", "Ikalus1988/MisakaNet")
TOKEN = os.environ.get("MISAKANET_TOKEN") or os.environ.get("GITHUB_TOKEN")
API_BASE = "https://api.github.com"


def _load_config():
    """读取 MisakaNet config.yaml"""
    config_path = os.path.join(PROJECT_ROOT, "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_graph():
    """初始化 Hub 的 Knowledge Graph（从 config.yaml 读取持久化路径）"""
    config = _load_config()
    graph_cfg = config.get("storage", {}).get("graph", {})
    persist_path = graph_cfg.get("persist_path", "./storage/knowledge_graph/graph.gpickle")
    persist_path = os.path.join(PROJECT_ROOT, persist_path)

    from storage.knowledge_graph import KnowledgeGraph
    kg = KnowledgeGraph(persist_path=persist_path)
    print(f"  [graph] loaded: {len(kg.graph.nodes)} nodes, {len(kg.graph.edges)} edges")
    print(f"  [graph] persist: {persist_path}")
    return kg


def gh_api(method, path, data=None):
    """调用 GitHub REST API"""
    import requests

    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "MisakaNet-HubPoller",
    }

    url = f"{API_BASE}/{path.lstrip('/')}"

    if method == "GET":
        resp = requests.get(url, headers=headers, timeout=15)
    elif method == "POST":
        resp = requests.post(url, headers=headers, json=data, timeout=15)
    elif method == "PATCH":
        resp = requests.patch(url, headers=headers, json=data, timeout=15)
    else:
        raise ValueError(f"unsupported method: {method}")

    if resp.status_code >= 400:
        print(f"  [warn] API error {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        return None
    if resp.status_code == 204:
        return {"status": "ok"}
    return resp.json()


def fetch_unprocessed_feedback():
    """获取所有未处理的反馈 Issues"""
    issues = gh_api("GET", f"/repos/{REPO}/issues?labels=feedback,unprocessed&state=open&sort=created&per_page=20")
    if issues is None:
        print("  [error] 无法获取 Issues。检查 TOKEN 和仓库权限。", file=sys.stderr)
        return []
    print(f"  未处理反馈: {len(issues)} 条")
    return issues


def parse_feedback(issue):
    """从 Issue body 解析反馈数据"""
    try:
        body = json.loads(issue["body"])
    except (json.JSONDecodeError, TypeError):
        print(f"  [warn] Issue #{issue['number']} body 解析失败，跳过", file=sys.stderr)
        return None

    required = ["node_id", "skill", "result", "scenario"]
    for field in required:
        if field not in body:
            print(f"  [warn] Issue #{issue['number']} 缺少字段 {field}，跳过", file=sys.stderr)
            return None

    return {
        "issue_number": issue["number"],
        "issue_url": issue["html_url"],
        "node_id": body["node_id"],
        "skill": body["skill"],
        "result": body["result"],
        "scenario": body["scenario"],
        "extra": body.get("extra", {}),
        "created_at": issue["created_at"],
    }


def update_knowledge_graph(kg, feedback):
    """更新 Hub 的 Knowledge Graph"""
    skill = feedback["skill"]
    result = feedback["result"]
    node_id = feedback["node_id"]

    weight_map = {"success": 1.0, "partial": 0.5, "failure": -0.2}
    delta = weight_map.get(result, 0)

    # 确保节点存在
    if not kg.graph.has_node(skill):
        kg.graph.add_node(skill, type="skill", name=skill, weight=0, usage_count=0)

    if not kg.graph.has_node(node_id):
        kg.graph.add_node(node_id, type="agent", name=node_id)

    # 更新 skill 节点权重（移动平均）
    old = kg.graph.nodes[skill].get("weight", 0)
    count = kg.graph.nodes[skill].get("usage_count", 0) + 1
    new_weight = (old * (count - 1) + delta) / count
    kg.graph.nodes[skill]["weight"] = round(new_weight, 4)
    kg.graph.nodes[skill]["usage_count"] = count
    kg.graph.nodes[skill]["last_used"] = datetime.now(timezone.utc).isoformat()

    # 更新 node → skill 边权重
    if kg.graph.has_edge(node_id, skill):
        old_edge = kg.graph.edges[node_id, skill].get("weight", 0)
        edge_count = kg.graph.edges[node_id, skill].get("count", 0) + 1
        new_edge_weight = (old_edge * (edge_count - 1) + delta) / edge_count
        kg.graph.edges[node_id, skill]["weight"] = round(new_edge_weight, 4)
        kg.graph.edges[node_id, skill]["count"] = edge_count
        kg.graph.edges[node_id, skill]["last_result"] = result
        kg.graph.edges[node_id, skill]["last_used"] = datetime.now(timezone.utc).isoformat()
    else:
        kg.graph.add_edge(node_id, skill, weight=delta, count=1, last_result=result,
                          last_used=datetime.now(timezone.utc).isoformat())

    kg.save()
    print(f"  [graph] {skill}: weight={kg.graph.nodes[skill]['weight']}, count={kg.graph.nodes[skill]['usage_count']}")
    return True


def mark_processed(issue_number, feedback, success):
    """回复 Issue 并标记为已处理"""
    status_emoji = "✅" if success else "⚠️"
    summary = f"{status_emoji} **Processed by Hub** (`{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}`)\n\n"
    summary += f"- Skill: `{feedback['skill']}`\n"
    summary += f"- Result: {feedback['result']}\n"
    summary += f"- Node: `{feedback['node_id']}`\n"
    summary += f"- Scenario: {feedback['scenario'][:80]}...\n\n"
    if success:
        summary += "Knowledge Graph updated."
    else:
        summary += "Graph update failed. See Hub logs."

    gh_api("POST", f"/repos/{REPO}/issues/{issue_number}/comments", {"body": summary})
    gh_api("PATCH", f"/repos/{REPO}/issues/{issue_number}", {
        "labels": ["feedback", "processed", f"node:{feedback['node_id']}", f"skill:{feedback['skill']}"],
        "state": "closed",
    })
    print(f"  [issue #{issue_number}] 已回复并关闭")


def main():
    print("=" * 55)
    print(f"  MisakaNet Hub Poller")
    print(f"  repo: {REPO}")
    print(f"  time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 55)

    if not TOKEN:
        print("[error] 请设置 MISAKANET_TOKEN 或 GITHUB_TOKEN 环境变量", file=sys.stderr)
        sys.exit(1)

    # 初始化 Knowledge Graph
    try:
        kg = _get_graph()
    except ImportError as e:
        print(f"[error] 无法加载 KnowledgeGraph: {e}", file=sys.stderr)
        print("  确保在 MisakaNet 项目根目录下运行本脚本", file=sys.stderr)
        sys.exit(1)

    # 检查 hook stats 并推送飞书（独立于 Issues，每次均执行）
    _check_hook_stats_and_notify()

    # 获取未处理反馈
    issues = fetch_unprocessed_feedback()
    if not issues:
        print("  没有未处理的反馈")
        kg.save()  # 确保持久化
        return

    for issue in issues:
        print(f"\n─ Issue #{issue['number']}: {issue['title']}")
        body = issue.get("body", "{}")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}

        if payload.get("type") == "inventory":
            # 清单变更处理
            node_id = payload.get("node_id", "unknown")
            skills = payload.get("skills", [])
            removed = payload.get("removed", [])

            for s in skills:
                if not kg.graph.has_node(s):
                    kg.graph.add_node(s, type="skill", name=s, weight=0.3, usage_count=0)
            for s in removed:
                if kg.graph.has_node(s):
                    kg.graph.nodes[s]["deprecated"] = True
                    kg.graph.nodes[s]["weight"] = 0

            kg.save()
            print(f"  [inventory] {node_id}: {len(skills)} active, {len(removed)} deprecated")
            mark_processed(issue["number"], {
                "skill": "inventory",
                "result": "success",
                "node_id": node_id,
                "scenario": f"sync inventory: {len(skills)} skills, {len(removed)} removed",
            }, True)
            continue

        feedback = parse_feedback(issue)
        if not feedback:
            continue
        print(f"  node: {feedback['node_id']}, skill: {feedback['skill']}, result: {feedback['result']}")
        success = update_knowledge_graph(kg, feedback)
        mark_processed(issue["number"], feedback, success)

    print(f"\n=== 完成: 处理 {len(issues)} 条反馈 ===")


def _check_hook_stats_and_notify():
    """读取 .hook_stats/，有新增数据则推飞书"""
    import glob

    stats_dir = os.path.join(PROJECT_ROOT, ".hook_stats")
    if not os.path.isdir(stats_dir):
        return

    # 读取上次已推送的时间戳
    state_path = os.path.join(stats_dir, ".last_seen.json")
    last_seen = {}
    if os.path.exists(state_path):
        try:
            last_seen = json.loads(open(state_path).read())
        except Exception:
            last_seen = {}

    # 读取所有节点统计
    stats_data = []
    any_new = False
    for f in sorted(glob.glob(os.path.join(stats_dir, "*.json"))):
        base = os.path.basename(f)
        if base.startswith("."):
            continue
        try:
            data = json.loads(open(f).read())
            node = data.get("node")
            updated = data.get("updated_at", "")
            # 只推送有新增数据的节点
            if node and updated and updated > last_seen.get(node, ""):
                stats_data.append(data)
                any_new = True
        except Exception:
            continue

    if not any_new:
        return

    # 推送到飞书
    config = _load_config()
    webhook = config.get("feishu", {}).get("webhook_url", "")
    # 如果 config 里是占位符或空，回退到环境变量
    if not webhook or "${" in webhook:
        webhook = os.environ.get("FEISHU_WEBHOOK_URL", "")
    if not webhook:
        print("[hook_stats] 未配置飞书 webhook，跳过")
        # 即使没有 webhook，也更新 last_seen 避免重复检查
    else:
        from sync.feishu_notifier import FeishuNotifier
        notifier = FeishuNotifier()
        notifier.send_hook_stats(stats_data, webhook)

    # 更新已推送时间戳
    for data in stats_data:
        node = data.get("node")
        updated = data.get("updated_at", "")
        if node and updated:
            last_seen[node] = updated
    with open(state_path, "w") as f:
        json.dump(last_seen, f, ensure_ascii=False, indent=2)
    print(f"[hook_stats] last_seen 已更新 ({len(stats_data)} 节点)")

    # lessons ↔ Graph 关联已拆除（空壳代码，从未真正工作过）
    # 待仲裁/图谱查询场景激活后重新实现

if __name__ == "__main__":
    main()

