# Publish Rhythm Guide

## Overview

Optimize publish timing based on traffic patterns to maximize engagement.

**Data source:** GitHub traffic analytics (Sun peak: 1,130 | Mon peak: 1,156 | Thu low: 523)

## Optimal Windows

| Window | Time | Rationale |
|--------|------|-----------|
| Sunday Evening | 8pm | Peak traffic, weekend browsing |
| Monday Morning | 9am | Peak traffic, work week start |
| Wednesday Afternoon | 2pm | Mid-week engagement |

## Weekly Workflow

### Saturday: Planning
- [ ] Review open PRs ready to merge
- [ ] Select content for next publish
- [ ] Prepare lesson/feature documentation

### Sunday/Monday: Publish
- [ ] Merge PR during optimal window
- [ ] Run `python3 scripts/publish_rhythm.py record --type lesson --title "..." --pr 123`
- [ ] Monitor initial engagement

### Tuesday/Wednesday: Measure
- [ ] Run `python3 scripts/publish_rhythm.py update-metrics`
- [ ] Check 48h response: stars, clones, requests
- [ ] Record observations

### Thursday: Review
- [ ] Run `python3 scripts/publish_rhythm.py report --days 7`
- [ ] Analyze patterns
- [ ] Adjust strategy if needed

## Metrics Tracking

### Key Metrics (48h window)
- **Stars delta**: New stars after publish
- **Clones**: Repository clones (interest indicator)
- **Requests**: API/site requests (engagement indicator)

### Recording

```bash
# After publish
python3 scripts/publish_rhythm.py record \
  --type lesson \
  --title "curl timeout behind corporate proxy" \
  --pr 1493

# After48h
python3 scripts/publish_rhythm.py update-metrics

# Weekly report
python3 scripts/publish_rhythm.py report --days 7
```

## Hypothesis Testing

**H₀:** Publish timing doesn't affect engagement
**H₁:** Publishing during peak windows increases stars/clones

**Test method:**
1. Alternate weeks: peak vs off-peak publishing
2. Compare 48h metrics
3. Statistical significance after 4 weeks

## Calendar View

```bash
python3 scripts/publish_rhythm.py calendar
```

## References

- [GitHub Traffic Analytics](https://github.com/Ikalus1988/MisakaNet/graphs/traffic)
- Issue #1348: Publish rhythm optimization
