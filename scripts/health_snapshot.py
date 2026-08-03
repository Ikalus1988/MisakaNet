#!/usr/bin/env python3
import urllib.request, datetime, sys

ENDPOINTS = {
    "Homepage": "https://misakanet.org",
    "/api/health": "https://misakanet.org/api/health",
    "/api/counter": "https://misakanet.org/api/counter",
    "/api/lessons": "https://misakanet.org/api/lessons",
    "/search/": "https://misakanet.org/search/",
    "Journey page": "https://misakanet.org/journey",
    "Registration": "https://misakanet.org/register"
}

today = datetime.datetime.now().strftime("%Y-%m-%d")
report = f"## Site Health Snapshot — {today}\n\n| Endpoint | Status | Notes |\n|----------|--------|-------|\n"
warnings = []

for name, url in ENDPOINTS.items():
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'HealthChecker'}), timeout=10) as r:
            status = '✅' if r.status == 200 else '⚠️'
            notes = f"HTTP {r.status}"
            if r.status != 200: warnings.append(f"{name}: HTTP {r.status}")
    except Exception as e:
        status = '⚠️'
        notes = str(e)
        warnings.append(f"{name}: {str(e)}")
    
    report += f"| {name} | {status} | {notes} |\n"

report += f"\nWarnings: {', '.join(warnings) if warnings else '(none)'}\n"

print(report)
