#!/usr/bin/env python3
"""MisakaNet 推荐链 — 查看推荐码 / 填写邀请码。

用法:
    python3 scripts/referral.py                # 查看我的推荐码
    python3 scripts/referral.py --apply=CODE   # 填写邀请码
    python3 scripts/referral.py --stats        # 查看推荐链统计
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from misakanet.profile import _load, _save, apply_referral, get_referral_code


def show_my_code():
    p = _load()
    code = get_referral_code()
    referred_by = p.get("referred_by", "")
    stage = p.get("stage", "newcomer")
    print(f"\n🔗 MisakaNet 推荐链")
    print(f"  {'='*40}")
    print(f"  你的推荐码:  {code}")
    print(f"  当前阶段:    {stage}")
    if referred_by:
        print(f"  邀请人:      {referred_by}")
    else:
        print(f"  邀请人:      未填写")
    print(f"\n  分享链接:")
    print(f"    git clone https://github.com/Ikalus1988/MisakaNet")
    print(f"    python3 scripts/referral.py --apply={code}")
    print()


def show_stats():
    """从 git log 统计推荐链数据。"""
    code = get_referral_code()
    try:
        r = subprocess.run(
            ["git", "log", "--all", "--oneline", "--grep=" + code, "--", "misakanet/profile.json"],
            capture_output=True, text=True, timeout=10,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        count = len(r.stdout.strip().split("\n")) if r.stdout.strip() else 0
        print(f"\n📊 推荐链统计")
        print(f"  {'='*40}")
        print(f"  推荐码:     {code}")
        print(f"  已邀请:     {count} 个节点")
        print(f"\n  credit 机制说明:")
        print(f"    • 被邀请节点首次贡献 lesson 时，邀请方获得 credit")
        print(f"    • credit 当前阶段: 记账中，后续版本兑现检索权重加成")
        print()
    except Exception as e:
        print(f"  统计失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="MisakaNet 推荐链")
    parser.add_argument("--apply", help="填写邀请码")
    parser.add_argument("--stats", action="store_true", help="查看推荐统计")
    args = parser.parse_args()

    if args.apply:
        if apply_referral(args.apply):
            print(f"  ✅ 已绑定邀请码: {args.apply.upper()}")
        else:
            print(f"  ⚠️ 绑定失败（可能已绑定或邀请码无效）")
    elif args.stats:
        show_stats()
    else:
        show_my_code()


if __name__ == "__main__":
    main()
