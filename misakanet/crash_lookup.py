"""崩溃 → 课程检索：先查 MisakaNet，查不到才留草稿（issue #3642）。

崩溃过去止步于墓碑：四个字段说明**什么崩了**，不说**怎么修好的**，所以墓碑只能变成
一门过不了门禁的草稿。这不是墓碑写得不够好，而是顺序错了——先问 MisakaNet：

    崩溃 → 用同一条错误检索 MisakaNet
              ├─ 命中   → 打印课程标题 + 链接（当场可用）
              └─ 未命中 → 留草稿，并明确说"没有现成课程"

检索本身**没有**在这里重写。度量用的是 `scripts/intake_bot.py` 里那一个：`precheck`
用加权 0..2 分（`_sim`）给错误打分，`decide` 把命中变成
`{id, title, url, sim, sim_norm, sim_scale}`。检索 API 的 BM25 `score` 是**另一个量**
——把两者混在一起，正是"命中"变成噪音的路径。

这个模块守住两条：

* **检索可以失败。** 崩溃处理器不能因为网络不通而崩：检索失败被记下来
  （`skipped_reason`），调用方退回草稿路径——那正是本 issue 之前的行为。
* **检索用的就是崩溃自己的错误文本**，去掉堆栈帧：帧里是函数名和文件名，不是失败本身，
  而它们会稀释命中判定要找的证据词（实测：Node 的 EACCES 崩溃，错误行打 0.667 命中，
  整段 snippet 直接不命中）。
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

__all__ = [
    "CrashLookup",
    "SearchFn",
    "format_hit",
    "format_no_hit",
    "lookup_crash",
    "search_lessons",
    "strip_stack_frames",
]


#: 一篇课程在站点上的地址。`intake_bot.decide` 用同一个模板。
LESSON_URL_TEMPLATE = "https://misakanet.org/lessons/{id}/"

#: 检索函数：吃一段错误文本，吐一篇课程（或 None）。可注入，所以三条分支都能离线测。
SearchFn = Callable[[str], "dict | None"]

#: 拉语料的上限（秒）。fatal-guard 在 5 秒后杀掉 handler
#: （packages/fatal-guard/src/lib/spawn-command.js:29 的 HANDLER_TIMEOUT_MS），
#: 所以检索必须在这个预算内完成——拉不到就跳过检索，行为与检索之前一致。
#: 实测：冷启动拉全量语料（516 篇）约 1 秒，热缓存 0.08 秒。
CORPUS_TIMEOUT_S = 3


class LookupUnavailable(Exception):
    """检索跑不起来（语料拉不到）——这不是"没有现成课程"，是根本没查。"""


# 堆栈帧行：它们命名的是函数和文件，不是失败本身。
#   JS     "    at openSync (node:fs:498:26)"
#   Python '  File "/app/main.py", line 12, in <module>'
#   Python 3.11+ 的定位条 "    |" 与脱字符 "    ^"
_STACK_FRAME_RE = re.compile(
    r"^\s*(?:"
    r"at\s+\S"                              # JS 帧
    r"|File\s+\""                           # Python 帧头
    r"|\^+"                                 # 指向出错表达式的脱字符
    r"|\|+"                                 # Python 3.11+ 帧条
    r"|Traceback \(most recent call last\):"  # Python traceback 头
    r"|During handling of the above exception"
    r"|The above exception was the direct cause"
    r")"
)


def strip_stack_frames(text: str) -> str:
    """去掉堆栈帧，留下陈述失败的那些行。

    检索用这个文本，草稿留的是完整现场（帧也是证据）。两者是同一段错误文本，
    区别只在噪声：帧里的 `loader`/`internal`/`anonymous` 会把命中判定要找的
    主体词挤掉——实测同一条 EACCES 崩溃，错误行命中 0.667，带帧的整段不命中。
    """
    kept = [line for line in (text or "").splitlines() if not _STACK_FRAME_RE.match(line)]
    return "\n".join(kept).strip()


@dataclass(frozen=True)
class CrashLookup:
    """一次崩溃检索的结果。

    `searched` 与 `hit` 分开，是因为"没查"和"查了没有"是两件事：
    前者是没有网络（照旧留草稿），后者是确实没有现成课程（也留草稿，但要说清楚）。
    """

    error_text: str
    hit: bool
    lesson: dict | None = None
    searched: bool = False
    skipped_reason: str | None = None


def search_lessons(
    error_text: str,
    *,
    sim_threshold: float | None = None,
    corpus: list | None = None,
) -> dict | None:
    """问那个已经校准好的命中判定：有没有课程已经回答了这次崩溃。

    命中返回课程 dict（`id`/`title`/`url`/`sim`/…），没命中返回 None。
    阈值默认就是 `intake_bot.DEFAULT_HIT_SIM`——这里不另设一个数；要换，
    必须带上实测理由（见 issue #3642 的讨论）。

    语料拉不到时抛 `LookupUnavailable`：**"没查成"和"查了没有"是两回事**，
    混成一句"没有现成课程"就是在骗人——调用方据此把两件事分开报。
    """
    # `misakanet/` 是可安装包，`scripts/` 不在其中——所以延迟导入，
    # 跟包里其它地方（misakanet/search/engine.py）一个写法。
    from scripts import intake_bot

    if corpus is None:
        # 语料由 intake_bot 自己拉、自己缓存（300 秒），这里只是把它显式拉出来，
        # 好让"拉不到"这件事能被当成"检索没跑成"报出去。decide() 内部会调用
        # 同一个函数，传了 corpus 就不会拉第二次。
        corpus = intake_bot._load_corpus(timeout=CORPUS_TIMEOUT_S)
        if not corpus:
            raise LookupUnavailable(
                f"the lesson corpus is not available (fetched within {CORPUS_TIMEOUT_S}s)")

    result = intake_bot.decide(
        error_text,
        source="fatal-guard",
        what_tried="",
        auto_intake=False,  # 崩溃处理器不提交 intake：它只负责"找得到 / 找不到"
        sim_threshold=intake_bot.DEFAULT_HIT_SIM if sim_threshold is None else sim_threshold,
        force=False,
        offline=False,
        corpus=corpus,
    )
    if result["decision"] != "hit":
        return None
    return result["lesson"]


def lookup_crash(
    error_text: str,
    *,
    search: SearchFn | None = None,
    offline: bool = False,
    sim_threshold: float | None = None,
    corpus: list | None = None,
) -> CrashLookup:
    """在 MisakaNet 里查这次崩溃。

    `search` 是接缝：传一个可调用对象，就能在没有网络、也不 spawn 任何东西的
    情况下测命中 / 未命中 / 无网络三条分支。默认是 `search_lessons`。
    """
    if offline:
        # 无网络：跳过检索，行为与本 issue 之前一致（留草稿）。
        return CrashLookup(error_text=error_text, hit=False, searched=False,
                           skipped_reason="offline")
    if search is None:
        search = functools.partial(search_lessons, sim_threshold=sim_threshold, corpus=corpus)
    try:
        lesson = search(error_text)
    except Exception as exc:  # noqa: BLE001 — 检索失败是规格内的降级，不是静默
        return CrashLookup(error_text=error_text, hit=False, searched=False,
                           skipped_reason=f"{type(exc).__name__}: {exc}")
    if not lesson:
        return CrashLookup(error_text=error_text, hit=False, searched=True)
    return CrashLookup(error_text=error_text, hit=True, lesson=lesson, searched=True)


def format_hit(lesson: Mapping) -> str:
    """命中时给的那一行：课程是什么、在哪读。"""
    title = str(lesson.get("title") or "").strip() or "(untitled lesson)"
    url = str(lesson.get("url") or "").strip() or LESSON_URL_TEMPLATE.format(
        id=lesson.get("id") or "")
    sim = lesson.get("sim")
    scale = lesson.get("sim_scale")
    score = ""
    if sim is not None:
        score = f"（sim={sim}" + (f"/{scale:g}" if isinstance(scale, (int, float)) else "") + "）"
    return f"💡 命中课程{score}：{title}\n   {url}"


def format_no_hit(draft_path: Path | None = None, *, search_note: str | None = None) -> str:
    """没命中时给的那一行：没有现成课程，草稿在哪。

    `search_note` 非空表示检索**没跑成**（无网络、拉不到语料）——那时候不能说
    "没有现成课程"：我们根本没查。`draft_path` 为 None 时也不能说"已留草稿"——
    没写就是没写。
    """
    if search_note:
        where = f"，已留草稿：{draft_path}" if draft_path is not None else "（未留草稿）"
        return f"❌ 检索未完成（{search_note}）{where}"
    if draft_path is not None:
        return f"❌ 没有现成课程，已留草稿：{draft_path}"
    return "❌ 没有现成课程（未留草稿）"
