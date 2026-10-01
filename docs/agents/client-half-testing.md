# Testing the DSH client half from a checkout

**Who this is for.** Someone who wants to look at MisakaNet inside DeepSeek Harness — the six seats
[bounty #2593](https://github.com/Ikalus1988/MisakaNet/issues/2593) asks about — without waiting for an npm
release and **without touching the harness profile they use every day**.

Sibling documents: [`docs/compatibility.md`](../compatibility.md) (which host lines were measured, and what
each seat is), [`docs/maintainer/client-half-acceptance.md`](../maintainer/client-half-acceptance.md) (the
per-surface acceptance list), [`docs/integration/deepseek-harness.md`](../integration/deepseek-harness.md)
(the tools-only install guide).

## 1. npm lags main — which surfaces you get depends on where you install from

`dsh plugin --profile web add misakanet` resolves the **published** package. The published package is
whatever `npm`'s `latest` points at, and that is not `main`:

```console
$ curl -sS https://registry.npmjs.org/misakanet | python3 -c "import json,sys;print(json.load(sys.stdin)['dist-tags'])"
{'latest': '2.40.0'}

$ git show origin/main:lib/client.js | wc -c
101175
$ git ls-tree origin/main locale/ lib/
100644 blob 60be061cc1a4b70b85d2788bd2fe6106ae6909e6	lib/client.js
100644 blob 4aa69d425c0c3ea17cf3e39c94770371e836abc4	locale/en.json
100644 blob 77338605276710463126b4823000004a1c3a6757	locale/zh.json
```

The 2.40.0 tarball's `lib/client.js` is **50,486 bytes** and carries **no `locale/` directory**. So:

| Where you install from | Surfaces you get |
| --- | --- |
| `misakanet` on npm (`latest` = **2.40.0**) | the 2.40.0 seats: the left-column entry, the page it opens, the conversation tab, the right-column pane, the tool-call rows, and the 👍/👎 action row |
| **this working tree** (`main`, ahead of npm) | the above **plus** everything merged since: `/misakanet` in the composer, the frame-wide toast, the sidebar-foot action, Settings → General, the plugin page, and the packaged Chinese/English locales |

The second row is what the bounty needs. The extra surfaces are carried by **2.41.0**, whose release PR is
[#2591](https://github.com/Ikalus1988/MisakaNet/pull/2591) — until that merges, the only way to see them is
to install from a checkout. Verify the shape of the gap yourself at any time:

```bash
npm view misakanet version                      # the published one
git -C <checkout> rev-parse --short HEAD        # the tree you are about to test
git -C <checkout> show HEAD:lib/client.js | wc -c
```

Related, and owned elsewhere: the README's per-surface version columns are
[#2640](https://github.com/Ikalus1988/MisakaNet/issues/2640); the disposable path is `dsh plugin add` with a
*directory*, shown below.

## 2. The one-command probe — run this first

The repository already ships the measurement that answers "does the browser half exist on my host". It
refuses any `DSH_HOME` outside the temp directory, boots a throwaway host, and writes its JSON even when it
fails:

```bash
python3 scripts/install_smoke.py dsh-client --repo . --out /tmp/install-dsh.json
```

`--serve` keeps that host running and prints its URL for you to click — a disposable host to take bounty
screenshots in, with no manual wiring:

```bash
python3 scripts/install_smoke.py dsh-client --repo . --serve
```

Measured on 2026-10-01 (`dsh 0.2.0-rc.2`, this repository's `main`):

```console
$ python3 scripts/install_smoke.py dsh-client --repo .
{
  "form": "dsh-client",
  "ok": true,
  "checks": [
    "empty DSH_HOME at /tmp/misakanet-dsh-smoke-380b811_ (never the owner's)",
    "`dsh plugin add` put misakanet in dsh.profile.bundles",
    "host booted on http://127.0.0.1:58615/ (startup check passed)",
    "boot graph entry: {\"id\": \"misakanet\", \"url\": \"plugins/??misakanet/client.js&rev=2bb1be0d9e3e\", \"rev\": \"2bb1be0d9e3e\", \"inject\": [\"@deepseek-ai/dsh-client-ui-chat\", \"@deepseek-ai/dsh-client-ui-conversation\", \"@deepseek-ai/dsh-client-ui-sidebar-right\", \"@deepseek-ai/dsh-client-ui-tool\"]}",
    "the host echoed the declared inject order (4 packages)",
    "the combo route serves lib/client.js verbatim (no build step, no chunk)",
    "the served bundle registers all 7 seats"
  ],
  "failures": []
}
```

That proves the bundle is installed, the host starts, and the seats are *registered*. It does **not** drive a
browser, so it cannot tell you a seat *renders* — that is what the manual path below is for, and what
#2593's screenshots are for.

## 3. The manual path, copy-pasteable

Do this in a checkout of the repository (`git clone https://github.com/Ikalus1988/MisakaNet.git`, or the
worktree you already have). No build step is needed: `lib/client.js` is served verbatim from the tree.

> **Never do this against your daily `~/.dsh`.** `dsh plugin --profile web add <path>` edits **that
> profile's** `package.json` and `bundles` list. Adding or removing a bundle while a host is running leaves
> it silently unloaded, and a broken bundle in a profile makes the host *refuse to start* and take every
> unrelated plugin in that profile with it. The `DSH_HOME` below is a throwaway directory for exactly that
> reason.

```bash
REPO=/path/to/your/MisakaNet            # the checkout you want to test
HOMEDIR=/tmp/dsh-client-half            # disposable — deleted in §6
PORT=41337

rm -rf "$HOMEDIR" && mkdir -p "$HOMEDIR"
export DSH_HOME="$HOMEDIR"
export npm_config_cache="$HOMEDIR/npm-cache"   # keep pnpm's cache inside the throwaway home too
```

**Install this working tree into the throwaway profile.** A *path* is a valid argument — that is what the
probe in §2 does:

```bash
dsh plugin --profile web add "$REPO"
```

Check what the profile now holds, instead of trusting the installer's exit code:

```bash
dsh plugin --profile web list
cat "$DSH_HOME/profiles/web/package.json"     # bundles should name misakanet
```

Observed on 2026-10-01 in a throwaway profile: a local install lands in that file as a **link**
(`"misakanet": "link:/path/to/your/MisakaNet"`), not a copied tarball. Practical consequence: the profile
points at your tree, so remove the plugin or delete the `DSH_HOME` when you are done with that tree.

### Seed one workspace before the first boot (this is the "composer never mounts" trap)

A completely fresh `DSH_HOME` has **zero** workspaces, so the composer mounts as its workspace chooser
instead of a composer — `[role=textbox]` is labelled `Choose workspace`, the body says `Choose a workspace to
start`. Nothing is broken and **nothing is logged**: the domain silently drops a workspace record that does
not satisfy its schema, and the chosen-looking symptom is a textbox nobody can type into.

The record needs `createdAt` and `updatedAt`. Without them it is rejected with no error; with them the host
creates the first session itself on page load, which is the way the host supports it. A/B measured on
2026-10-01 (`dsh 0.2.0-rc.2`), with those two fields as the only difference:

| seeded record | `[role=textbox]` aria-label | page body |
| --- | --- | --- |
| missing `createdAt`/`updatedAt` | `Choose workspace` | `No sessions yet` / `Choose a workspace to start` |
| with them | `Describe what you want to build, / commands, @ files or sessions` | composer is live |

Do not try to *drive* the chooser as a workaround: adding a workspace through the real UI goes through a
native directory picker that a headless browser cannot open, and driving the chooser is what hid the
rejected-record bug for a day (`docs/maintainer/handoff-2026-09-30-ext.md` §11.2).

```bash
python3 - "$HOMEDIR" "$REPO" <<'PY'
import json, pathlib, sys, uuid
from datetime import datetime, timezone

home, repo = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]).resolve()
now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
wid = str(uuid.uuid4())
(home / "storages" / "workspace.json").write_text(json.dumps({
    "unit": {"name": "workspace", "version": 2},
    "global": {"initialized": True, "workspaceIds": [wid],
               "archivedSessionIds": [], "pinnedSessionIds": []},
    "tables": {"workspaces": {wid: {
        "path": str(repo), "title": repo.name, "sessionIds": [],
        "createdAt": now, "updatedAt": now}}},
}), encoding="utf-8")
print("seeded workspace", wid, "->", repo)
PY
```

### Boot the host

```bash
dsh --profile web --no-open --port "$PORT" >"$HOMEDIR/host.log" 2>&1 &
grep -o "http://127.0.0.1:$PORT/?token=[A-Za-z0-9_-]*" "$HOMEDIR/host.log" | head -1
```

The printed URL carries a one-time token — open the **full URL including `?token=…`**. It is a credential
for your throwaway host, so keep it out of screenshots.

### The two first-run dialogs swallow every click

A fresh profile opens two blockers before the app is usable, and both *must* be dismissed or every later
click lands on the dialog:

1. **Preview Notice** → click **Continue** (this is the host's preview acknowledgement, not MisakaNet's);
2. **Add an API key to get started** → click **Configure later** — testing the client half needs no
   credentials.

Both headings and both button labels are the host's own strings (`dsh-client-ui-settings-models`), and both
were observed on a fresh throwaway home on 2026-10-01. Then check the composer is the real one:

```bash
# in the page: the composer is live when [role=textbox] is labelled
#   "Describe what you want to build, / commands, @ files or sessions"
# if it still says "Choose workspace", the seeded record was rejected — re-read the section above.
```

## 4. Seat checklist

Take these in order; each row says what it looks like when it is there. The bounty's screenshots are the
left-column entry + the page it opens (seats 1–2), and one session surface with data in it (seats 3–6 after a
search). The bounty's table is written against 2.40.0, and the first five rows below are the seats that
release already carried:

| Seat (bounty #2593) | Slot | In 2.40.0? |
| --- | --- | --- |
| 1. Left column, under `Plugins` | `sidebar.panellist` | ✅ |
| 2. `main` page | `main` | ✅ |
| 3. Conversation tab ring | `conversation.view` | ✅ |
| 4. Right column pane | `sidebar.right.pane.tab` | ✅ |
| 5. Tool call rows | `tool.call.toolview` | ✅ |
| 6. Assistant action row | `conversation.chat.assistant-actions` | ✅ |

The full slot-vs-scope table, with the host's own contract text quoted, is in
[`docs/compatibility.md`](../compatibility.md).

| Seat (bounty #2593) | What to look for |
| --- | --- |
| 1. Left column, under `Plugins` | a permanent **MisakaNet** entry, drawn as an icon; it is a shortcut, not the panel. If the column is collapsed, screenshot the rail icon. |
| 2. `main` page | what that entry opens — the browser-scoped MisakaNet view. |
| 3. Conversation tab ring | a **MisakaNet** tab beside Chat and Trajectory. |
| 4. Right column pane | the same panel as a pane, beside the other tools. |
| 5. Tool call rows | one row per `misakanet_search` / `misakanet_submit_intake` call, on the tool card. |
| 6. Assistant action row | 👍 / 👎 on a finalized answer that used a lesson. |

Seats 1–6 are the 2.40.0 set. On a **checkout** install you should also see the surfaces that are not in
2.40.0 yet — `/misakanet` in the composer, the frame-wide toast after a search, the sidebar-foot action,
Settings → General, and the localized Chinese/English copy. Report those as *found* only if you installed
from a checkout; on the npm 2.40.0 package their absence is expected, not a bug.

To get data into a session surface (seat 3–6), ask the agent to search, e.g. *"search MisakaNet for
`pip install timeout`"*: the search row and the panel then have content, and the toast appears once the
search returns lessons.

## 5. What to report, and where

Evidence is the deliverable — command plus output, not a description:

* comment on [#2593](https://github.com/Ikalus1988/MisakaNet/issues/2593) with the screenshots and the probe
  JSON from §2, plus your environment (`dsh --version`, OS, fresh or pre-existing profile);
* report anything that broke through `misakanet_submit_intake` (`kind="missing_lesson"`) and link the
  returned `dedup_key`;
* "the host refuses to start" is a finding worth its own line — paste the last lines of `$HOMEDIR/host.log`.

## 6. Cleanup

```bash
lsof -ti tcp:$PORT | xargs -r kill      # kill by port, never by a pattern that could match your own shell
dsh plugin --profile web remove misakanet   # while the host is stopped (see the warning in §3)
rm -rf "$HOMEDIR"                        # the whole disposable profile, cache and sessions
unset DSH_HOME npm_config_cache
```

`DSH_HOME` is exported for that shell; if you opened a new shell to test, it is already gone. Removing a
bundle from a **running** host leaves it silently unloaded — stop the host first, or use the GUI.

If you used a git worktree for the checkout, remove it from the repository it was created in:

```bash
git -C /path/to/MisakaNet worktree remove --force /tmp/wf-yourname
```
