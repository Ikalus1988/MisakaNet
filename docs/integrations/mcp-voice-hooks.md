# MCP Voice Hooks

Play a sound — and, for the results that matter, show a short desktop notification — when
MisakaNet answers: one cue when a search hits, a different one when it does not.

The server has always sent a `voice` field in its tool results (`lesson-found`,
`failure-warning`, `connect-success`, `pair-success`); this hook turns that field into a sound
and/or a notification through the host's `PostToolUse` event. It is **opt-in**, and the same
command that wires everything else can install it:

```bash
npx @misaka-net/misakanet-setup --voice     # Claude Code: adds a PostToolUse hook
```

Which cues make a sound and which also notify is one table, documented under
[通知 vs 语音](#通知-vs-语音) below. Switch any of it off later without uninstalling anything:

```bash
export MISAKANET_VOICE=0        # runtime mute: sound *and* notifications
export MISAKANET_NOTIFY=0       # notifications only; the sounds stay
```

`npx @misaka-net/misakanet-setup --uninstall` removes the hook entry, the player and the cues.

## What gets installed

| Piece | Where | Why there |
|---|---|---|
| `voice-hook.mjs` (the player) | `~/.misakanet-agent/voice/` | a hook must survive an `npx` cache eviction, so it is copied out of the package |
| the four cues (`*.mp3`) | same directory | shipped inside the npm tarball: an install must not depend on reaching GitHub |
| a `PostToolUse` entry | `~/.claude/settings.json` | **with `matcher: "*"`** — see below |

Nothing else is installed: the cue → sound/notification table lives in the hook itself, and the
only file it ever creates is the small `state/voice-notified.json` ledger for the two cues that
notify once per machine (see [通知 vs 语音](#通知-vs-语音)). No new binary, no new dependency,
no new switch at install time — the same single `--voice`.

## Cues

| Cue | Sound | When |
|---|---|---|
| `lesson-found` | `lesson-found.mp3` | `misakanet_search` returned at least one lesson |
| `failure-warning` | `failure-warning.mp3` | search came back empty / `no_match`, or the read quota refused |
| `connect-success` | `connect-success.mp3` | `misakanet_get_lesson` returned a lesson |
| `pair-success` | `pair-success.mp3` | a usage receipt was recorded |

Canonical audio lives in `docs/assets/voice/`; `packages/misakanet-setup/scripts/copy-hook.mjs`
copies it into the tarball at pack time.

## 通知 vs 语音

语音只在**你坐在电脑前**的时候有用：它告诉你"工具跑了",但不告诉你"跑出了什么",而且你一旦戴着耳机、
静音或者走开两分钟,它就完全失效。桌面通知补上另一半——它把"检索命中了""链路是通的"这类**值得抬眼一次、
但你不会主动去查**的结果,放进系统的通知中心。代价是通知比声音更容易变成骚扰,所以规则写在代码里、也写在这里:

| Cue | 语音 | 桌面通知 | 为什么 |
|---|---|---|---|
| `lesson-found` | ✅ `lesson-found.mp3` | ✅ `MisakaNet：找到一条相关经验` | 命中课程是最值得抬眼一次的事 |
| `failure-warning` | ✅ `failure-warning.mp3` | ❌ **不通知** | 落空是负面结果,而且每次空搜都会发生;agent 本来就会告诉你,弹窗只是噪音 |
| `connect-success` | ✅ `connect-success.mp3` | ✅ `MisakaNet：已连接`,**仅本机第一次** | 每次取课程都通知会把人逼疯,第一次让你确认"链路是通的",之后靠语音 |
| `pair-success` | ✅ `pair-success.mp3` | ✅ `MisakaNet：已连接`,**仅本机第一次** | 同上:回执是背景事件,重复通知没有新信息 |

- **去重**按 cue 各自记一次,记在 `~/.misakanet-agent/state/voice-notified.json`(临时文件 + rename
  原子写入)。写不进去(只读 home、磁盘满)不会报错、也不会影响 agent —— 最坏情况是重启后多弹一次。
- 通知文案**短、只陈述事实**,不写营销话术,而且和表一起放在代码里,以后要做多语言时是同一处。
- `MISAKANET_NOTIFY=0` 期间**不记**去重状态:你关掉通知之后再打开,第一次 `connect-success` 仍然会通知。

### 平台支持

| 平台 | 语音 | 通知 | 用什么 |
|---|---|---|---|
| macOS | ✅ `afplay` | ✅ | `osascript -e 'display notification … with title "MisakaNet"'` |
| Linux(带桌面的发行版) | ✅ `paplay`/`ffplay`/`mpv`/`mpg123`/`cvlc` | ✅ | `notify-send -a MisakaNet`(freedesktop 通知规范) |
| WSL2 | ✅(走 Windows 侧 PowerShell,理由见下) | ✅ | 同上,`powershell.exe` 优先 |
| Windows(原生) | ⚠️ 只有 PowerShell 那条路可走 | ⚠️ 同左 | PowerShell `NotifyIcon` 气泡,**没有** PowerShell 时静默降级 |
| 无头服务器 / SSH / 容器 | ✅ 装了播放器就有 | ❌(没人可通知) | 找不到通知命令就跳过,不报错 |

关于 Windows 的"PowerShell toast":真正的 WinRT toast(`Windows.UI.Notifications`)需要一个注册过
AUMID 的开始菜单快捷方式,裸 `powershell.exe` 调用它通常直接以 "Element not found" 失败——而钩子只能
把它吞掉,于是你什么也看不到、也不知道为什么。所以这里用的是**不依赖任何模块**的
`System.Windows.Forms.NotifyIcon` 气泡,Windows 10/11 会由操作中心按 toast 呈现。这就是那条"文档化的
降级路径"。

### 如何彻底安静

按静音程度从轻到重(都不需要卸载、都是环境变量):

```bash
export MISAKANET_NOTIFY=0     # 只关通知:仍有声音
export MISAKANET_VOICE=0      # 语音 + 通知全关(装了也等于没装)
npx @misaka-net/misakanet-setup --uninstall   # 彻底移除:hook 条目、播放器和音频
```

`MISAKANET_VOICE=0` 是总开关:语音和通知一起关。想在"完全无声"和"有声音"之间切换时不必重装,
把这两行写进 shell profile 即可。要做一次**不发声、不弹窗**的预演,用 dry run:

```bash
echo '{"voice":"connect-success"}' | MISAKANET_VOICE_DRY_RUN=1 node ~/.misakanet-agent/voice/voice-hook.mjs
# → connect-success
#   sound=connect-success.mp3 (would play)
#   notify=would send "MisakaNet：已连接" (first time only)
```

dry run 是**只读**的:它报告会做什么,但不播、不弹、也不记去重状态——所以你可以随便试,不会把
"第一次通知"提前用掉。

### 安全:cues 只用来查表

cue 是**服务端**给你的字符串。它在本文件里的唯一用途是当**查表用的键**:`CUE_ACTIONS[cue]`。
它不会被拼进命令行、不会被拼进路径、不会交给 shell,也不会作为参数传给任何进程——播放器、参数、
`*.mp3` 文件名、通知文案,全部是代码里写死的字面量。表里没有的 cue(包括 `x; rm -rf /`、
`$(curl …)`、或者 5000 个字符的 cue)就等于**没有任何动作**:钩子直接退出 0,连一个进程都不会起。
`workers/agent-autostart-hook.test.mjs` 用一个把 PATH 全换成记录桩的测试来断言这一点(未知/恶意 cue
必须让记录保持为空),另一条测试把表本身钉死成"恰好这四个 cue"。

## Three things the real machine taught us (2026-09-16, WSL2)

1. **A `PostToolUse` entry without `matcher` never fires.** The same command with
   `"matcher": "*"` fired on every tool call. The hook filters by the `voice` field itself, so
   matching everything costs nothing — but without the matcher the installer ships a hook that
   is silent forever, and nothing tells you.
2. **The host hands the MCP result to the hook as an escaped JSON *string***, nested under
   `tool_response`. A player that only walks objects finds nothing there; this one re-parses
   nested JSON strings (bounded depth).
3. **On WSL, prefer the Windows side.** `ffplay` cannot open an ALSA card in WSL at all
   ("cannot find card '0'"), so a Linux-first player order installs a hook that never makes a
   sound. The player therefore tries `powershell.exe` first when `WSL_DISTRO_NAME` is set,
   playing the file through `\\wsl.localhost\<distro>\…` with `presentationCore`'s
   `MediaPlayer` — verified by asking it for the duration it had loaded (4.2s for
   `lesson-found`).

Player order after that: `afplay` (macOS) → `paplay` → `ffplay` → `mpv` → `mpg123` → `cvlc`.
`aplay` is deliberately **not** in the list: the assets are MP3 and aplay plays only raw/WAV, so
the older shell script's ALSA branch was silent on exactly the machines that reached it.

## Debugging it

```bash
echo '{"voice":"lesson-found"}' | MISAKANET_VOICE_DRY_RUN=1 node ~/.misakanet-agent/voice/voice-hook.mjs
# → lesson-found                                          (no audio device, no desktop needed)
#   sound=lesson-found.mp3 (would play)
#   notify=would send "MisakaNet：找到一条相关经验"

echo '{"voice":"lesson-found"}' | MISAKANET_VOICE_DEBUG=1 node ~/.misakanet-agent/voice/voice-hook.mjs
# → cue=lesson-found player=powershell.exe file=/home/…/lesson-found.mp3 notify=powershell.exe "MisakaNet：找到一条相关经验"
```

The dry run prints what it *would* do for both halves and executes neither; the debug line says
what actually happened — including `notify=none (no notifier available on this platform)` and
`notify=already sent at …` when the one-time cue has fired before.

A hook must never look like a tool failure, so the player and the notifier swallow every error
(a missing binary, a denied dbus, a read-only `$HOME`), print nothing on the normal path, and the
hook always exits 0.

## Legacy: the shell script (clone users)

`scripts/misakanet_voice_hook.sh` predates the installer and is kept for people running from a
clone. Two caveats, both real: it parses stdin with `python`, which is missing on many Linux/WSL
boxes (this repo has that bug on record — `python3` is the one that exists), and its Linux branch
has no MP3-capable player. Prefer the Node player; you can point a hook straight at it:

```json
{
  "hooks": {
    "PostToolUse": [
      { "matcher": "*", "hooks": [ { "type": "command",
        "command": "node /path/to/MisakaNet/integrations/agent-autostart/voice_hook.mjs" } ] }
    ]
  }
}
```
