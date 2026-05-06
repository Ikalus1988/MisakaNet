#!/usr/bin/env python3
"""
MisakaNet Standby Poller (备 Hub 节点侧)
=========================================
主 Hub（Windows）离线时接管 Feishu hook stats 推送。
只读 .hook_stats/，不碰 Issues/Graph。

用法:
  # 直接运行（前台，调试用）
  python3 misakanet/scripts/standby_poller.py

  # Cron 模式（每 5 分钟）
  */5 * * * * python3 /path/to/MisakaNet/misakanet/scripts/standby_poller.py

依赖:
  pip install requests pyyaml
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent / ".." / ".."
STATS_DIR = PROJECT_ROOT / ".hook_stats"
STATE_FILE = STATS_DIR / ".standby_last_seen.json"

# 启动延迟（秒）：让主 Hub 先推，避免重复
STARTUP_DELAY = 300  # 5 分钟


def _load_config():
    """读取 MisakaNet config.yaml"""
    import yaml
    config_path = PROJECT_ROOT / "config.yaml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def _git_pull():
    """拉取最新 .hook_stats/"""
    os.chdir(str(PROJECT_ROOT))
    subprocess.run(["git", "pull", "--ff-only", "origin", "main"],
                   capture_output=True, timeout=30)


def _read_last_seen() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_last_seen(data: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _check_new_stats() -> list[dict]:
    """返回有新数据的节点列表"""
    last_seen = _read_last_seen()
    new = []
    for f in sorted(STATS_DIR.glob("*.json")):
        if f.name.startswith("."):
            continue
        try:
            data = json.loads(f.read_text())
            node = data.get("node", "")
            updated = data.get("updated_at", "")
            if node and updated and updated > last_seen.get(node, ""):
                new.append(data)
        except Exception:
            continue
    return new


def _push_feishu(stats: list[dict]):
    """推送到飞书"""
    config = _load_config()
    webhook = config.get("feishu", {}).get("webhook_url", "")
    # 如果 config 里是占位符或空，回退到环境变量
    if not webhook or "${" in webhook:
        webhook = os.environ.get("FEISHU_WEBHOOK_URL", "")
    if not webhook:
        print("[standby] 未配置飞书 webhook，跳过")
        return

    lines = ["📊 MisakaNet Hook 统计 (备 Hub)\n"]
    for s in stats:
        node = s.get("node", "?")
        triggers = s.get("triggers", {})
        hits = s.get("hits", {})
        active = [(c, triggers.get(c, 0), hits.get(c, 0))
                   for c in ["network", "pip", "permission", "disk", "package_conflict", "model_output"]
                   if triggers.get(c, 0) > 0]
        if active:
            lines.append(f"节点 {node}:")
            icons = {"network": "🔴", "pip": "🟡", "permission": "🔵", "disk": "🟣",
                     "package_conflict": "🟠", "model_output": "⚪"}
            for cat, t, h in active:
                lines.append(f"  {icons.get(cat, '⚪')} {cat}  {t}次  lessons 有答案{h}次")
        else:
            lines.append(f"节点 {node}: 无触发")

    payload = {"msg_type": "text", "content": {"text": "\n".join(lines)}}

    import requests
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        print(f"[standby] Feishu 推送 {'✅' if resp.status_code == 200 else '❌'}")
    except Exception as e:
        print(f"[standby] Feishu 推送失败: {e}")


def main():
    print(f"=== MisakaNet Standby Poller ===")

    # 启动延迟
    if "--no-delay" not in sys.argv:
        # 检查是否是首次启动
        state = _read_last_seen()
        if not state:
            print(f"  首次启动，等待 {STARTUP_DELAY}s 让主 Hub 先推送...")
            time.sleep(STARTUP_DELAY)

    # 拉取最新数据
    _git_pull()
    print(f"  git pull OK")

    # 检查新数据
    new_stats = _check_new_stats()
    if not new_stats:
        print(f"  无新数据")
        return

    print(f"  发现 {len(new_stats)} 个节点有新数据")
    _push_feishu(new_stats)

    # 更新已推送时间戳
    state = _read_last_seen()
    for s in new_stats:
        node = s.get("node", "")
        updated = s.get("updated_at", "")
        if node and updated:
            state[node] = updated
    _save_last_seen(state)
    print(f"  last_seen 已更新")


if __name__ == "__main__":
    main()
