#!/usr/bin/env python3
"""
⚡ Absorb Merged Journey Reports into Actionable Docs & Issues (#868)
Processes user journey reports and extracts actionable issue tickets and documentation updates.
"""

import os
import json
import re

class JourneyReportAbsorber:
    def __init__(self, reports_dir="docs/user-journeys"):
        self.reports_dir = reports_dir

    def parse_report_content(self, text):
        lines = text.strip().split("\n")
        title = lines[0].replace("#", "").strip() if lines else "Untitled Journey"
        actionables = []

        for line in lines:
            if line.strip().startswith("- [ ]") or line.strip().startswith("- [x]") or "TODO:" in line:
                cleaned = re.sub(r"^-\s*\[[ xX]\]\s*", "", line.strip()).replace("TODO:", "").strip()
                actionables.append(cleaned)

        return {
            "title": title,
            "actionables": actionables,
            "total_actionables": len(actionables)
        }

    def generate_github_issue(self, parsed):
        issue_title = f"[Actionable] {parsed['title']}"
        body_items = "\n".join([f"- [ ] {item}" for item in parsed['actionables']])
        issue_body = f"""## User Journey Feedback & Action Items
Extracted from merged user journey report: **{parsed['title']}**

### Action Items:
{body_items}

/claim #868
"""
        return {
            "title": issue_title,
            "body": issue_body,
            "count": len(parsed['actionables'])
        }
