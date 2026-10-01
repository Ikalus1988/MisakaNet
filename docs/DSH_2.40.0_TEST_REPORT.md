# DSH 2.40.0 browser-half test report

For [issue #2593](https://github.com/Ikalus1988/MisakaNet/issues/2593). Credit only. Paste the command and the output underneath. No write-up in place of output.

The browser half starts at 2.40.0. 2.39.0 has no UI to capture. If the version is older than 2.40.0, stop.

## Version

```console
$ npm view misakanet version
```

Paste the version npm prints.

## Host

Throwaway profile only. Start the host fresh. The profile must not already have this plugin.

Leave `DSH_HOME` unset, or point it at a directory you just created under `/tmp`. Do not point it at a profile you use for anything else.

Install one of these ways:

- `dsh plugin --profile web add misakanet`
- the GUI wizard

Restart the host after you install, remove, or upgrade. These two are easy to misread as a missing plugin, and they are not new bugs:

- Installing or removing from the CLI while the host is running leaves the plugin unloaded until you restart.
- The host keeps serving the bundle it built at startup. Restart the host, or toggle the plugin, after an upgrade.

| key | value |
| --- | --- |
| `dsh --version` | |
| OS | |
| host started fresh | |
| profile already had the plugin | |
| install path | |
| browser, theme, locale | |

- [ ] install path is filled in
- [ ] `dsh.profile.bundles` is pasted below, or a plugin-page screenshot is attached

```text

```

## Probe

From this checkout:

```console
$ python3 scripts/install_smoke.py dsh-client --repo . --out /tmp/install-dsh.json
```

Paste the `checks` object and the `failures` array from `/tmp/install-dsh.json`. Strip home-directory prefixes and usernames if a path contains them. Do not paraphrase.

A pass needs `failures` to be empty. The checks should show the bundle was added, the host started, the boot graph has the plugin with its declared inject order, the bytes served match `lib/client.js`, and the seats that registered.

## Six seats

Attach one screenshot per seat to the issue. Do not add the images to the repo. If two seats are the same screen, one file is enough. Note that in the file column.

Seats 3 through 6 need a session that already contains a search. If the pane stays empty, write the query you ran and what you got back. A blank seat with no note fails the report.

| # | Seat | Capture | File | Done |
| --- | --- | --- | --- | --- |
| 1 | Plugin entry | Left column, under `Plugins`, the `MisakaNet` entry | `seat-1-plugins.png` | [ ] |
| 2 | Main page | Page opened from that entry. The rail icon counts if the column is collapsed | `seat-2-main.png` | [ ] |
| 3 | Session tab | `MisakaNet` tab on the conversation tab ring | `seat-3-tab.png` | [ ] |
| 4 | Session questions | "what this session asked", and it is not empty | `seat-4-asked.png` | [ ] |
| 5 | Side pane | Right column for that session | `seat-5-pane.png` | [ ] |
| 6 | Call actions | Call rows, including the 👍👎 action row | `seat-6-actions.png` | [ ] |

If the probe names the seats differently, paste its list here and say which row above each name maps to. Do not retitle the screenshots to force a match.

## Intake

Submit one missing lesson through `misakanet_submit_intake` with `kind` set to `missing_lesson`.

Paste the result and the `dedup_key` link. If it errors, paste the error and the arguments you passed. Leave that first attempt in the report.

## Pass

Pass only when every line below is true.

- [ ] printed version is 2.40.0 or newer
- [ ] probe `failures` is empty
- [ ] all six seats are checked, and the screenshots are on the issue
- [ ] intake result is pasted

If any line is still open, this report fails. Quote the first failing check and stop.
