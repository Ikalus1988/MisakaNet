#!/usr/bin/env python3
"""MisakaNet 推荐链 — 查看推荐码 / 填写邀请码。

用法:
    python3 scripts/referral.py                # 查看我的推荐码
    python3 scripts/referral.py --apply=CODE   # 填写邀请码
    python3 scripts/referral.py --stats        # 查看推荐链统计
"""
import argparse
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from misakanet.profile import _load, _save, apply_referral, get_referral_code

# Every client on this machine can read this file — the npm installer, the bootstrap
# installer and the CLI all look in `~/.misakanet-agent` for `client_id` and `token` — so it
# is where an invited node records the code that invited it. `apply_referral` keeps writing the
# clone-local profile too (that is where this node's own code lives); this file is the part
# that can leave the machine (#1996).
REFERRAL_FILE = Path.home() / ".misakanet-agent" / "referral_code"
ENDPOINT = "https://misakanet.org/api/referrals"
REFERRAL_RE = re.compile(r"^[A-Za-z0-9]{4,16}$")


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


def record_referral_for_clients(code: str) -> bool:
    """Write the inviting code where every client can read it.

    The value travels from a file into an API request, so it is shape-checked here rather than
    trusted: `apply_referral` accepts anything at least four characters long for backwards
    compatibility, and this is the boundary that decides what is allowed to leave the machine.
    """
    code = (code or "").strip()
    if not REFERRAL_RE.match(code):
        return False
    try:
        REFERRAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        REFERRAL_FILE.write_text(code + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


def _server_count(code: str) -> int | None:
    """The server-side invitation count, or None when it cannot be read.

    None is deliberately distinct from 0: "nobody has used your code yet" and "I could not ask" are
    different answers, and printing 0 for the second is how a broken counter passes for a fact.
    """
    if not code:
        return None
    try:
        with urllib.request.urlopen(f"{ENDPOINT}?code={urllib.parse.quote(code)}", timeout=10) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    invited = payload.get("invited")
    return int(invited) if isinstance(invited, int) else None


def show_stats():
    """从 git log 统计推荐链数据。

    这套机制只在一种情况下计数：有人把 `misakanet/profile.json` **提交进历史**（它曾是被跟踪
    文件），于是 `--grep=<code> -- misakanet/profile.json` 能数出用过这个码的节点。2026-09-21
    起该文件**不再被跟踪**（#1991：它是每台机器的状态，而且每次检索都会被改写），所以：

    * 历史里的旧记录仍然数得到；
    * **此后不会再增加**，因为新的 `referred_by` 永远进不了 git 历史。

    这不是这里少了一行代码，而是推荐链从来没有服务端记录：worker 完全不认识 referral。要让
    "已邀请 N 个节点" 真的成立，得在注册时把推荐码记到服务端（D1），见 issue #1996。
    """
    code = get_referral_code()
    server = _server_count(code)
    try:
        r = subprocess.run(
            ["git", "log", "--all", "--oneline", "--grep=" + code, "--", "misakanet/profile.json"],
            capture_output=True, text=True, timeout=10,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        history = len(r.stdout.strip().split("\n")) if r.stdout.strip() else 0
        print(f"\n📊 推荐链统计")
        print(f"  {'='*40}")
        print(f"  推荐码:     {code}")
        if server is None:
            print(f"  已邀请:     读不到（服务端不可达或响应形状不对）—— 读不到就不编一个数字")
        else:
            print(f"  已邀请:     {server} 个节点（服务端计数：{ENDPOINT}）")
        print(f"  历史值:     {history} 个节点（2026-09-21 之前的 git 历史统计，已停用）")
        print(f"  说明:       服务端在**注册时**记一次：被邀请方的客户端带上")
        print(f"              ~/.misakanet-agent/referral_code；新节点 +1，续期同一节点不重复计。")
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
        # Only when it is code-shaped: the same rule the server applies. A value that fails it would
        # be silently ignored at registration, which is worse than being told now.
        if record_referral_for_clients(args.apply):
            print(f"  已记录到 {REFERRAL_FILE}（各客户端注册时会带上它）")
        else:
            print(f"  ⚠️ 形状不像推荐码（4-16 位 A-Za-z0-9），只写入了本地 profile")
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
