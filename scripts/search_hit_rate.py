#!/usr/bin/env python3
"""命中率的分母：聚合 worker 记录的检索信号（issue #1779）。

worker 侧现在给**每一次完成的检索**写一行 `search_signals`（命中 solved=1，
未命中 solved=0），并由只读端点 `GET /api/search-signals/stats` 把窗口内的
`solved` / `created_at` 返回出来。这个脚本把这些行聚合成：

    total / hit / miss / hit_rate / legacy_rows

用法::

    python3 scripts/search_hit_rate.py                    # 最近 7 天
    python3 scripts/search_hit_rate.py --since 30         # 最近 30 天
    python3 scripts/search_hit_rate.py --json             # 机器可读
    python3 scripts/search_hit_rate.py --url http://127.0.0.1:8787/api/search-signals/stats

只用标准库，只读：除了一次 GET 之外不碰服务端，也不会写任何东西。

字段定义、这个数字能说明什么、怎么回滚，见 docs/maintainer/search-metrics.md。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_ENDPOINT = "https://misakanet.org/api/search-signals/stats"
DEFAULT_SINCE_DAYS = 7

# 这个脚本**测不到**的东西。文档里同样写了一份，这里跟着一起打印：命中率最容易被
# 过度解读，所以宁可每次跑都提醒一次。
CAVEATS = [
    "只统计 worker 结算并返回结果的检索：被限流(429)、缺 query、课程加载失败等提前返回的请求不在分母里。",
    "solved 只表示“这次检索返回了 ≥1 条结果”，不表示结果有用，也不表示 agent 采纳了课程。",
    "分母是“我们的语料回答我们的查询”，不是终端用户的生产力：它不能证明“提效”。",
    "缺 solved 的旧格式行按“未命中”处理（保守），所以 legacy_rows > 0 时命中率被低估。",
    "端点最多返回固定行数（truncated=true 时这个数字只是下界）。",
    "端点不返回 query 文本，所以本脚本不能按查询或 domain 拆分。",
    "只覆盖走 worker 的 misakanet_search；本地 stdio MCP 与网站检索页不在其中。",
]


def solved_flag(value) -> bool | None:
    """把一行的 `solved` 解析成 True/False；旧格式（没有该字段）返回 None。

    D1 存的是整数 0/1，JSON 里也可能是布尔，两种都认；其它值一律当作“不知道”，
    由调用方按未命中处理——保守方向，绝不会凭空抬高命中率。
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return None


def aggregate(rows) -> dict:
    """把行聚合成 total / hit / miss / hit_rate / legacy_rows。

    `legacy_rows` = 没有 `solved` 字段（或为 null）的行，按未命中计入 `miss`，
    同时单独计数，好让维护者知道这段窗口里有多少条是老格式。
    """
    total = hit = miss = legacy = 0
    for row in rows or []:
        total += 1
        flag = solved_flag(row.get("solved")) if isinstance(row, dict) else None
        if flag is None:
            # 不是对象／没有 solved／值不认识 —— 都归入 legacy，且按未命中计。
            legacy += 1
            miss += 1
        elif flag:
            hit += 1
        else:
            miss += 1
    hit_rate = None if total == 0 else round(hit / total, 4)
    return {"total": total, "hit": hit, "miss": miss, "hit_rate": hit_rate, "legacy_rows": legacy}


def fetch_payload(endpoint: str, days: int, token: str | None = None, timeout: float = 30.0) -> dict:
    """读只读统计端点。窗口由服务端按 `days` 在 SQL 里过滤，脚本不自己筛时间。"""
    url = f"{endpoint}{'&' if '?' in endpoint else '?'}days={int(days)}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "MisakaNet-search-hit-rate/1.0"},
    )
    if token:
        # 端点目前是开放的（与 POST /api/search-signal 同一姿态），不需要令牌；
        # 但若以后收紧，同一个 token 走这两个头即可（X-Sync-Token 是 /api/search-index 用的）。
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("X-Sync-Token", token)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (固定 https 端点)
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or "rows" not in payload:
        raise RuntimeError(f"端点返回的不是预期结构（缺少 rows）: {str(payload)[:200]}")
    if not isinstance(payload.get("rows"), list):
        raise RuntimeError("端点返回的 rows 不是数组")
    return payload


def report(payload: dict, endpoint: str, days: int) -> dict:
    """把端点载荷变成最终结果字典（文本与 --json 共用同一份算术）。"""
    stats = aggregate(payload.get("rows"))
    return {
        **stats,
        "source": payload.get("source") or "unknown",
        "url": endpoint,
        "days": days,
        "truncated": bool(payload.get("truncated")),
        "caveats": list(CAVEATS),
    }


def format_text(result: dict) -> str:
    total = result["total"]
    rate = "n/a（窗口内没有样本）" if result["hit_rate"] is None else f"{result['hit_rate'] * 100:.1f}%"
    lines = [
        f"source          : {result['source']}",
        f"url             : {result['url']}",
        f"window          : 最近 {result['days']} 天（UTC，服务端过滤）",
        f"total           : {total}",
        f"hit             : {result['hit']}",
        f"miss            : {result['miss']}",
        f"hit_rate        : {rate}",
        f"legacy_rows     : {result['legacy_rows']}（没有 solved 字段的旧格式行，已按未命中计入 miss）",
    ]
    if result["truncated"]:
        lines.append("warn            : 端点行数被截断，这个数字只是下界")
    if total == 0:
        lines.append("")
        lines.append("样本不足，等待数据：窗口内还没有记录到的检索，请不要引用任何命中率。")
    lines.append("")
    lines.append("测不到的部分（务必连着一起读）:")
    lines.extend(f"  - {caveat}" for caveat in CAVEATS)
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="聚合 MisakaNet 检索命中率（issue #1779）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--since", type=int, default=DEFAULT_SINCE_DAYS, metavar="DAYS",
                        help=f"统计窗口的天数（默认 {DEFAULT_SINCE_DAYS}）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--url", default=DEFAULT_ENDPOINT, help=f"统计端点（默认 {DEFAULT_ENDPOINT}）")
    parser.add_argument("--token", default=os.environ.get("MISAKANET_TOKEN", ""),
                        help="可选令牌（默认取 $MISAKANET_TOKEN）；端点当前开放，不带也能跑")
    args = parser.parse_args(argv)

    days = max(1, int(args.since))
    try:
        payload = fetch_payload(args.url, days, token=(args.token or None))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError, RuntimeError) as exc:
        print(f"取数失败：{exc}", file=sys.stderr)
        print("没有拿到任何行，因此这次**测不出**命中率（不是 0%）。", file=sys.stderr)
        print("可检查：端点是否可达、worker 是否绑定了 D1（wrangler.toml 的 MISAKANET_D1）、"
              "以及窗口内是否真的还没有任何检索被记录。", file=sys.stderr)
        return 2

    result = report(payload, args.url, days)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
