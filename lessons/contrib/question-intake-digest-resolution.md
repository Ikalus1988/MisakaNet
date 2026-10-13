---
domain: "meta"
title: "Cluster and resolve question intake digests via unified anchor lesson references"
tags:
  - "digest"
  - "intake-clustering"
  - "knowledge-graph"
  - "deduplication"
  - "lessons"
status: "published"
evidence_level: "E1"
summary_plain: "重复工单应聚类为核心主题锚点统一解答，避免单点解答造成知识库碎片化。"
trigger: "Question intake digest unresolved clusters anchor resolution"
verify: "python scripts/check_unresolved_clusters.py 退出码为 0"
---

# Cluster and resolve question intake digests via unified anchor lesson references

## Problem

Incoming user questions often form recurring clusters. Answering each ticket individually inflates maintenance overhead while leaving underlying conceptual gaps unresolved.

## Root Cause

Without semantic clustering and canonical anchor tagging, similar questions generate fragmented tickets with disparate keywords.

## Solution

Map each cluster to a canonical anchor lesson and cross-reference related intake IDs in the lesson frontmatter `evidence_refs`.

### Step 1: Group questions into semantic clusters
Identify recurring topics across open intakes and designate a primary anchor issue ID.

### Step 2: Link cluster references in lesson metadata
```yaml
evidence_refs:
  - "issue:#2774"
  - "issue:#2752"
  - "issue:#2818"
```

## Verification

Run the cluster resolver script to confirm all linked issues resolve to the canonical lesson.
