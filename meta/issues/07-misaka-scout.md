## 🧠 Task Background

An automated intelligence-gathering pipeline turns OpenClaw / browser-use / hermes-agent failures into MisakaNet lessons without human intervention. This task builds the first two links of that chain:

1. **Scout** — daily crawl of fresh GitHub Issues from target repos
2. **Diagnose** — pipe extracted error signatures through `search_knowledge.py --heal` to measure coverage

---

### 📋 Requirements

Write a Python script `scripts/misaka_scout.py` that:

1. Accepts a target GitHub repo + label filter (e.g., `--repo OpenClaw/OpenClaw --label bug`)
2. Fetches recent open issues via GitHub API (`requests`-free: use `gh api` CLI or stdlib `urllib`)
3. Extracts the error signature from each issue body using `_parse_error_signature()` logic
4. Runs each signature through `search_knowledge.py --heal --from-file <tmpfile>`
5. Outputs a summary report:

```
=== MisakaNet Scout Report ===
Target: OpenClaw/OpenClaw (label: bug)
Issues scanned: 23
Issues with matchable signatures: 14
  → of which covered by existing lessons: 6
  → of which uncovered (new harvest targets): 8
Top domains needed: playwright (3), wsl (2), timeout (2)
```

---

### 🛠️ Verification

The script must pass:

```bash
python3 scripts/misaka_scout.py --dry-run --repo Ikalus1988/MisakaNet --label bug
```

Dry-run mode prints what it would do without making any API calls (use a local fixture).

---

### 💎 Rewards

- 🟢 **Auto-Merge** on passing CI (DCO + pytest + schema validation)
- 🏆 **Leaderboard**: +2 Lesson Count, featured in Active Nodes wall

---

### Labels

`status:competition`, `ring-2`, `scout`, `heal`
