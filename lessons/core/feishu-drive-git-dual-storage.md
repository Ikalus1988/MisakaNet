{
  "title": "Feishu Drive + Git Dual Storage for Non-Technical Team Collaboration",
  "domain": "devops",
  "source": "ericjia",
  "status": "draft",
  "tags": [
    "feishu",
    "git",
    "file-sync",
    "team-collaboration",
    "non-technical-users",
    "cloud-storage",
    "change-management"
  ],
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "domain_expert": "ericjia",
  "verified_date": ""
}
---

# Feishu Drive + Git Dual Storage for Non-Technical Team Collaboration

## Problem

Technical teams using Git for version control need a way to share files (reports, dashboards, databases) with non-technical stakeholders (engineers, managers) who don't use GitHub/GitLab. Pure Git solutions exclude non-technical users from the collaboration loop.

## Root Cause

Git is powerful for version control but has high barrier to entry for non-technical users. Cloud storage (Feishu Drive, Dropbox, OneDrive) is accessible to everyone but lacks version management features (diff, PR, branch). Teams need both: Git for version control, cloud storage for distribution.

## Solution

Use Git as the source of truth for code/data, and Feishu Drive as a distribution layer for non-technical stakeholders.

### Architecture

```
Local Git Repo                    Feishu Drive (Distribution)
├── 02_scripts/                   ├── reports/ (current versions)
├── 03_outputs/                   ├── archive/ (old versions)
├── CHANGELOG.md                  ├── scripts/
├── b2_robot.db                   ├── database/
└── .git/                         └── CHANGELOG.md
        ↓                               ↑
    git commit                    sync script (manual/automated)
        ↓                               ↓
    local files ─────────────→ Feishu Drive
```

### Step 1: Define Directory Structure

Feishu Drive folder structure:
```
project-handoff/
├── reports/              # Current reports (latest hash only)
├── archive/              # Old report versions
├── scripts/              # Scripts (optional, Git has them)
├── database/             # Compressed DB files
├── CHANGELOG.md          # Human-readable change log
├── Handoff.md            #交接文档 (file index + rules)
└── README.md             # Directory description
```

### Step 2: Establish Change Management Rules

1. **Git commit message format**: `<type>: <description>`
   - Types: fix, docs, db, reports, refactor, feat
   - Example: `fix: repair KUN process_upper_limit data`

2. **CHANGELOG dual-write**: Update both Feishu CHANGELOG and local CHANGELOG.md for every important change.

3. **File cleanup rules**:
   - Current reports: keep only latest hash version
   - Old reports: move to archive/
   - Duplicate files: delete, keep 1
   - .DS_Store: always delete

### Step 3: Sync Workflow

Manual sync (current):
```bash
# 1. Generate report locally
python3 generate_report.py

# 2. Copy to Feishu Drive
cp 03_outputs/reports/FO_report.md /path/to/feishu-drive/reports/

# 3. Update CHANGELOG
echo "## $(date +%Y-%m-%d) Report generated" >> CHANGELOG.md
git add . && git commit -m "reports: generate FO report"
```

Automated sync (future):
```bash
# sync_to_feishu.py
# - Diff local vs Feishu Drive
# - Copy changed files
# - Generate CHANGELOG entry
# - Optional: notify via Feishu webhook
```

## Verification

1. Check Feishu Drive has latest files after sync
2. Check CHANGELOG exists in both locations
3. Check Git commit history matches Feishu file timestamps
4. Test: modify local file → sync → verify Feishu shows update

## Notes

- This is NOT a replacement for Git — it's a distribution layer for non-technical users
- Feishu Drive has no diff/PR/branch features — it's a "crippled repository"
- The sync gap (manual copy) is the main weakness — automation helps but doesn't fully solve it
- Compare with pure Git: slower (2-3x), but better for non-technical collaboration
- Use case: teams with mixed technical/non-technical members, report-heavy projects

### When to Use This Pattern

- Team has non-technical stakeholders (engineers, managers)
- Reports need frequent sharing and discussion
- Data security requires dual backup (local Git + cloud)
- Audit compliance needs operation logs
- Project lifecycle > 6 months

### When NOT to Use

- Pure technical team (everyone uses GitHub)
- Need CI/CD automation
- Code-heavy project (docs are secondary)
- Fast iteration (efficiency priority)
