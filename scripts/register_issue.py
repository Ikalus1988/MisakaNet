#!/usr/bin/env python3
"""Welcome a registration issue, and write **no node number** anywhere.

Why this exists (2026-09-23, issue #2106)
-----------------------------------------
`register.yml` used to assign the next node number itself: read `data/counter.json`, add one,
commit, push to `main`. Two things are wrong with that, and only the first is new.

1. **The push no longer works.** The ruleset on `main` (23826057, `bypass_actors: []`) requires
   three status checks on any commit that lands there, and GitHub evaluates them on a direct push
   too. Three registration runs died there on 2026-09-22 (35749203103 / 35761772072 / 35764549504),
   each retrying five times, each logging

       remote: - 3 of 3 required status checks are expected.

   and the two steps after it — the welcome comment and the close — were `skipped`.

2. **It should never have been the writer.** `data/counter.json` is documented in
   `sync-node-counter.yml` as *the offline-checkable copy* of the counter that `/api/counter`
   serves from the worker's KV; `scripts/node_status.py` calls the KV value authoritative, and the
   worker (`node_counter` in `register-proxy-sw.js`, plus `workers/email-register/`) is what
   actually allocates a node. Issue #1683 was filed because the file and KV had drifted apart
   while both claimed to be the truth. Assigning a number in a workflow is that same second-writer
   defect, still live: on 2026-09-23 the file said 11047 while KV said 11777.

The fix is not to move the write behind a pull request. It would put ten minutes of required checks
on the person registering, and two registrations in flight would each read the same
`data/counter.json` from `main` and hand out the **same number**. It is to stop writing: the node
number is allocated by the worker when the user calls `misakanet_register`, which is the path the
MCP and email channels already use, and `sync-node-counter.yml` mirrors KV back into the file.

So this job keeps only what it is uniquely good at: telling a person, in the place where they
already are, exactly how to register and what to expect. It reads the live count (a read, not a
write), posts one comment, labels the issue and closes it.

The number is deliberately **not** promised in the comment. The old copy said "你是第 N 位接入者"
with N taken from the file, which counted issue-openers rather than registered nodes, and the node
id it implied was not the one the user got from their own `misakanet_register` call. A public issue
is also the wrong place for a credential: whatever identifies a node's token has to stay private
(`client_id` reuse returns the same token, so publishing a `client_id` would publish the token), and
that is why this script never allocates on the issue's behalf.

`build_welcome()` refuses to return a body containing something that looks like a token. The guard
is here rather than in a review checklist because this comment is public: one careless edit that
"helpfully" prints the credential would publish it to everyone who reads the issue.

Usage
-----
    python3 scripts/register_issue.py --issue 1234          # welcome, label, close
    python3 scripts/register_issue.py --issue 1234 --dry-run # print the comment, write nothing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# The node offset lives in one place. The node *count* is no longer published anywhere (2026-09-26),
# but the arithmetic still is: this script writes the registrant's node number into the welcome comment
# and `docs/index.html` estimates it from the same counter, so both keep reading one constant.
from scripts.sync_lesson_count import NODE_OFFSET  # noqa: E402

API_ROOT = "https://api.github.com"
COUNTER_URL = "https://misakanet.org/api/counter"
# Cloudflare answers 403 to urllib's default User-Agent, which is how `node_status.py` learned the
# same lesson on 2026-09-15: the request has to identify itself.
USER_AGENT = "misakanet-register-issue/1.0 (+https://misakanet.org)"

MARKER = "<!-- misakanet-welcome -->"
REGISTRATION_LABEL = "registration"
REGISTERED_LABEL = "registered"

NODE_ID_RE = re.compile(r"\bMisaka\d{5}\b")
# A credential this script must never publish. `mcp_` is the prefix the worker issues.
TOKEN_RE = re.compile(r"mcp_[A-Za-z0-9_-]{8,}")


class RegisterError(RuntimeError):
    """A precondition or an API call that must stop the run."""


# ────────────────────────────── pure decisions (unit-tested) ──────────────────────────────


def is_registration(title: str, labels: list[str]) -> bool:
    """Is this issue a registration request?

    The label is the mechanical signal: `.github/ISSUE_TEMPLATE/register.yml` sets
    `labels: [registration]` itself, so a template-made issue is recognised without guessing at
    words. The title prefixes are the legacy shapes (`join: yashraj4`, `[JOIN] Hermes Agent`),
    matched as **prefixes** rather than as substrings — which is the defect this replaces. The
    guard used to be `contains(title, 'register')`, and on 2026-09-22 that fired the registration
    job on three unrelated issues of mine ("docs(site): registration copy still frames registration
    as the way in", "fix(api): `client_id` is a credential in practice — the register reuse path
    returns the stored token", …), which then failed at the push step and looked like a broken
    registration path.
    """
    if REGISTRATION_LABEL in {str(label).strip().lower() for label in labels or []}:
        return True
    text = (title or "").strip().lower()
    return (
        text == "join"
        or text.startswith("[join]")
        or text.startswith("join:")
        or text.startswith("join：")
        or text.startswith("join ")
    )


def node_id_in(*texts: str | None) -> str | None:
    """A node id already allocated by another channel (email/web), if the issue carries one."""
    for text in texts:
        found = NODE_ID_RE.search(text or "")
        if found:
            return found.group(0)
    return None


def usable_current(current: object) -> int | None:
    """`/api/counter`'s `current` if it is a usable int, else None.

    The endpoint is public and outside our control, so a payload of the wrong shape returns None
    rather than raising: a welcome comment that omits the count is still worth posting, and a
    registration must never fail because a display line could not be filled in.
    """
    if not isinstance(current, int) or isinstance(current, bool) or current < NODE_OFFSET:
        return None
    return current


def display_count(current: object) -> int | None:
    """The number every public surface shows: `current - NODE_OFFSET` (live: 11777 → 1777)."""
    usable = usable_current(current)
    return None if usable is None else usable - NODE_OFFSET


def next_node_id(current: object) -> str | None:
    """The node id the worker is about to hand out — `Misaka{current + 1}`.

    This is what `allocateNodeCounter()` in `workers/register-proxy-sw.js` does: read
    `node_counter` from KV, write back `current + 1`, and name the node `Misaka{current + 1}`. So
    reading the public counter and adding one names the number the *next* registration receives,
    without allocating anything.

    It is deliberately an **estimate** and the comment says so. The alternative — and what this
    file replaces — was worse in a way that was visible to users: the old workflow assigned the
    number from `data/counter.json`, which trailed KV by 730 on 2026-09-23 (file 11047, KV 11777),
    so the site's "✅ 已分配 Misaka11048" named a node that had not existed for months and was not
    the node the user's own `misakanet_register` call returned.
    """
    usable = usable_current(current)
    return None if usable is None else f"Misaka{usable + 1:05d}"


def refuse_credentials(text: str) -> None:
    """Refuse to publish anything that looks like a node token.

    The comment this script writes is public. One careless edit that "helpfully" prints the
    credential would publish it for every reader of the issue, so the check lives here, next to the
    text, rather than in a review checklist nobody runs before a 3 a.m. rerun.
    """
    found = TOKEN_RE.search(text)
    if found:
        raise RegisterError(
            f"refusing to post: the welcome text contains what looks like a node token "
            f"({found.group(0)[:8]}…). This comment is public — a credential in it is a credential "
            "published."
        )


def build_welcome(*, node_id: str | None = None, node_count: int | None = None,
                  next_id: str | None = None) -> str:
    r"""The comment. Public text: no credential, no promise the workflow cannot keep.

    Three things are pinned by tests because all three were wrong before:

    * it must not offer reads as the reason to register (the 5-reads-a-day cap was removed on
      2026-09-18 and reads have been unlimited since);
    * the node id it names must match what the **site polls for** (`docs/index.html` looks for
      `/节点代号.*?[*]{2}(Misaka\d+)[*]{2}/` in this issue's comments and flips the page from
      "⏳ 分配中" to "✅ 已分配" — a comment without that shape leaves the user watching a spinner
      for three minutes, which is what a naive "stop writing the counter" change would have done);
    * and when the id is the worker's *next* number rather than one already allocated, the text has
      to say so, because the number the user's own `misakanet_register` call returns is the
      authoritative one.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [MARKER, "🧠 **欢迎加入御坂网络！**", ""]
    if node_id:
        lines += [f"你的节点代号：**{node_id}**（本 issue 已由邮件 / Web 通道分配）。", ""]
    elif next_id:
        lines += [
            f"你的节点代号：**{next_id}**",
            "",
            "ⓘ 这是 worker 计数器里的**下一个号**（实时读 `/api/counter`），不是本 workflow 分配的 —— "
            "编号只由 worker 的 KV 计数发放，这里只读不写。真正落到你名下的是你调用 "
            "`misakanet_register` 时返回的 `node_id`；中间若有别人注册，号会后移一两个。",
            "",
        ]
    if node_count is not None:
        lines += [
            f"当前网络：**{node_count}** 个已注册节点（实时值，来自 worker 的 KV 计数）。",
            "",
        ]

    lines += [
        "## 拿到你的 token（一次 HTTP 调用，免账号）",
        "",
        "一次 HTTP 调用，**不需要账号、不需要 clone、不需要下载**：",
        "",
        "```bash",
        "curl -sS https://misakanet.org/mcp \\",
        "  -H 'Content-Type: application/json' \\",
        "  -H 'Accept: application/json' \\",
        "  -H 'MCP-Protocol-Version: 2025-06-18' \\",
        "  -H 'Origin: https://misakanet.org' \\",
        "  -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":"
        "{\"name\":\"misakanet_register\",\"arguments\":"
        "{\"agent_type\":\"<你的 agent 名字>\",\"client_id\":\"<你自己生成的随机 UUID>\"}}}'",
        "```",
        "",
        "返回里的两个字段就是全部：",
        "",
        "| 字段 | 是什么 |",
        "|---|---|",
        "| `node_id` | 你的节点代号（例如 `Misaka10074`）——节点本身就是这个编号 |",
        "| `token` | `mcp_…`，30 天有效；放 `Authorization: Bearer mcp_...` 头里用 |",
        "",
        "**`client_id` 请自己生成一个随机 UUID 并留好**：以后用同一个值调用都会回到同一个节点"
        "（响应里 `reused: true`）并顺带续期，所以「这个节点复用过的知识」才会累积在一处。"
        "`client_id` **按凭据对待**（2026-09-24 更正）：出示它就会拿回该节点的 token，"
        "所以别人知道了就能冒用——用随机 UUID、自己保管，不要拿主机名 / 工作区 id 这类可猜的值派生。",
        "",
        "> ⚠️ **`token` 当密码对待**：只放进 `Authorization` 头，不要贴到 issue、日志或仓库里。"
        "本评论不会替你贴出任何 token。",
        "",
        "## 读不需要注册，也不限次数（2026-09-18 起）",
        "",
        "`misakanet_search` / `misakanet_get_lesson` **匿名即可用、不限次数**，只有反爬突发保护"
        "（同一地址每分钟的上限，三个入口共用一个窗口）。注册解锁的是**写入类**工具"
        "（`write_lesson` / `preflight`），不是「读得更多」。",
        "",
        "所以如果你只是想查东西，现在就可以直接查 —— 无命中时会返回 `no_match` 和一条"
        "可直接调用的报料指引（gap → issue 闭环）：",
        "",
        "```bash",
        "curl -sS https://misakanet.org/mcp \\",
        "  -H 'Content-Type: application/json' \\",
        "  -H 'Accept: application/json' \\",
        "  -H 'MCP-Protocol-Version: 2025-06-18' \\",
        "  -H 'Origin: https://misakanet.org' \\",
        "  -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":"
        "{\"name\":\"misakanet_search\",\"arguments\":"
        "{\"query\":\"pip install timeout or SSL error\",\"top\":3}}}'",
        "```",
        "",
        "### 三条实测过的细节",
        "",
        "- **`Origin` 头**：缺席放行；**带错值会 403 `invalid Origin`**（MCP 规范的防 DNS rebinding）。"
        "照上面写就对了。",
        "- **客户端偏好流式**时，把 `Accept` 换成 `application/json, text/event-stream` 并给 curl 加 `-N`："
        "服务端以 `event: message` 分块返回，内容与普通 JSON 完全一致。",
        "- **第一次调用就返回 `Rate limit`**：那是突发保护（共享出口 IP 很容易撞上），不是配额用完了；"
        "带上 `token` 就不再受它影响。",
        "",
        "## 贡献：第一次提交也不需要账号",
        "",
        "检索无果就是知识盲区。直接匿名报料（服务端去重后自动开 issue，进人工 triage）：",
        "",
        "```bash",
        "curl -sS https://misakanet.org/mcp \\",
        "  -H 'Content-Type: application/json' \\",
        "  -H 'MCP-Protocol-Version: 2025-06-18' \\",
        "  -H 'Origin: https://misakanet.org' \\",
        "  -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":"
        "{\"name\":\"misakanet_submit_intake\",\"arguments\":"
        "{\"problem\":\"<你的失败与修复>\",\"source\":\"<你的节点名>\"}}}'",
        "```",
        "",
        "<details><summary>离线 / 无网络时的替代路径</summary>",
        "",
        "下载索引（约 1.1 MB）后自行检索 —— 慢一些，但不需要任何出网调用：",
        "",
        "```",
        "https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main/data/lessons.json",
        "```",
        "",
        "</details>",
        "",
        "---",
        "",
        f"> 本评论由 `register.yml` 自动生成（{today}），它只读取实时计数、发评论、打标签、关 issue —— "
        "**不写任何节点编号**：编号由 worker 的 KV 计数统一发放，镜像回仓库是 `sync-node-counter.yml` 的事。",
    ]

    body = "\n".join(lines) + "\n"
    refuse_credentials(body)
    return body


# ────────────────────────────── side effects ──────────────────────────────


class GitHub:
    def __init__(self, repo: str, token: str):
        self.repo = repo
        self.token = token

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = path if path.startswith("http") else f"{API_ROOT}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"token {self.token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", USER_AGENT)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read().decode()
        except urllib.error.HTTPError as e:
            raise RegisterError(f"{method} {path} -> HTTP {e.code}: {e.read().decode()[:300]}") from None
        except urllib.error.URLError as e:
            raise RegisterError(f"{method} {path} -> {e.reason}") from None
        return json.loads(raw) if raw.strip() else {}

    def issue(self, number: int) -> dict:
        return self.request("GET", f"/repos/{self.repo}/issues/{number}")

    def upsert_comment(self, number: int, body: str) -> str:
        """Post the welcome once; a later run edits that same comment instead of adding another.

        `reopened` and a maintainer re-dispatching both land here, and two identical welcome
        comments on one issue is the kind of noise a person notices and a script does not.
        """
        existing = self.request("GET", f"/repos/{self.repo}/issues/{number}/comments?per_page=100")
        for comment in existing:
            if MARKER in (comment.get("body") or ""):
                self.request("PATCH", f"/repos/{self.repo}/issues/comments/{comment['id']}",
                             {"body": body})
                return f"updated comment {comment['id']}"
        created = self.request("POST", f"/repos/{self.repo}/issues/{number}/comments", {"body": body})
        return f"posted comment {created.get('id')}"

    def add_label(self, number: int, label: str) -> str:
        self.request("POST", f"/repos/{self.repo}/issues/{number}/labels", {"labels": [label]})
        return f"added label {label}"

    def close(self, number: int) -> str:
        self.request("PATCH", f"/repos/{self.repo}/issues/{number}", {"state": "closed"})
        return "closed"


def fetch_node_counter(url: str = COUNTER_URL) -> int | None:
    """The live `current` from the worker's counter, or None. Never fatal.

    None costs the comment its count line and its node-id estimate; it must not cost a
    registration, so every failure here is a warning.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode())
    except Exception as e:  # noqa: BLE001 — any failure means "no count in the comment"
        print(f"::warning::could not read {url}: {e}")
        return None
    current = usable_current(payload.get("current"))
    if current is None:
        print(f"::warning::{url} returned no usable current: {payload!r}")
    return current


def step_summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text.rstrip() + "\n")
    except OSError:
        pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--issue", type=int, required=True, help="issue number to welcome")
    p.add_argument("--repo", default=os.environ.get("GH_REPO") or os.environ.get("GITHUB_REPOSITORY", ""))
    p.add_argument("--dry-run", action="store_true", help="print the comment; call no write API")
    p.add_argument("--force", action="store_true",
                   help="welcome an issue that does not look like a registration")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.repo:
        print("::error::no repository: set GITHUB_REPOSITORY or pass --repo")
        return 1
    gh = GitHub(args.repo, os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", ""))

    try:
        issue = gh.issue(args.issue)
    except RegisterError as e:
        print(f"::error::cannot read issue #{args.issue}: {e}")
        return 1

    labels = [l.get("name", "") for l in issue.get("labels") or []]
    title = issue.get("title") or ""
    if not args.force and not is_registration(title, labels):
        # The old guard fired on any title containing "register", which is how three unrelated
        # issues got a red registration run on 2026-09-22. Saying so in the log is the point: the
        # run is cheap and its reason should be readable.
        print(f"issue #{args.issue} is not a registration (labels={labels}, title={title!r}) — nothing to do")
        step_summary(f"### Not a registration\n\n#{args.issue} carries no `{REGISTRATION_LABEL}` "
                     f"label and its title is not a `join` shape. No comment, no label, no close.")
        return 0

    node_id = node_id_in(title, issue.get("body"))
    current = fetch_node_counter()
    next_id = None if node_id else next_node_id(current)
    try:
        body = build_welcome(node_id=node_id, node_count=display_count(current), next_id=next_id)
    except RegisterError as e:
        print(f"::error::{e}")
        return 1

    if args.dry_run:
        print(body)
        return 0

    if not gh.token:
        print("::error::no GH_TOKEN/GITHUB_TOKEN in the environment")
        return 1

    actions = []
    try:
        actions.append(gh.upsert_comment(args.issue, body))
        if REGISTERED_LABEL not in labels:
            actions.append(gh.add_label(args.issue, REGISTERED_LABEL))
        if issue.get("state") == "open":
            actions.append(gh.close(args.issue))
    except RegisterError as e:
        print(f"::error::welcoming issue #{args.issue} failed: {e}")
        return 1

    print(f"issue #{args.issue}: " + "; ".join(actions))
    step_summary(
        f"### Welcomed #{args.issue}\n\n"
        + "\n".join(f"- {a}" for a in actions)
        + f"\n- node id in the comment: "
        + (node_id and f"{node_id} (already allocated by another channel)"
           or next_id and f"{next_id} (the worker's next number — not allocated here)"
           or "none (the counter could not be read)")
        + f"\n- live count: {display_count(current) if current is not None else 'unavailable'}"
        + "\n- **no commit**: the node counter lives in the worker's KV; `sync-node-counter.yml` "
          "mirrors it into the repository."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
