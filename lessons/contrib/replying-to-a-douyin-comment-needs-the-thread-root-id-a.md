---
title: "Replying to a Douyin comment needs the thread ROOT id; a comment's own id is only the root when it is top-level"
domain: "api"
tags:
  - "douyin"
  - "comment"
  - "api"
  - "reply_id"
  - "thread-root"
  - "nested-reply"
  - "notification-payload"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4220"
summary_plain: "Posting a reply through the Douyin web comment endpoint refused with \"cannot determine the thread root for this cid\"…"
trigger: "Replying to a Douyin comment needs the thread ROOT id; a comment's own id is only the root when it is top-level. Posting a reply through the Douyin web…"
verify: "With the root passed explicitly the reply was accepted (HTTP 200, cid returned) and the response echoed server_reply_id equal to the intended root, and the client reported the reply target as the…"
provenance:
  issue: "#4220"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Posting a reply through the Douyin web comment endpoint refused with "cannot determine the thread root for this cid", while a naive retry that simply passed the target comment id came back HTTP 200 and looked successful. For a level-2 comment that result would be a brand-new top-level comment: accepted by the server, visibly wrong in the thread.

## Root Cause

The publish endpoint has two different fields. reply_comment_id must be the thread root (the first top-level comment of that thread), while reply_to_reply_id points at the specific level-2 comment being answered. For a top-level comment the root happens to be the comment itself, which is why the naive retry "worked"; for a nested reply the root is an ancestor that cannot be guessed, and passing the comment's own id silently changes the semantics instead of failing loudly.

## Fix

Classify the target comment before sending, from the notification payload rather than a hot-ordered comment list. In the comment/@ notification object an empty reply_comment plus an empty level1_comment (and empty root_author / root_text) means the mention sits on a top-level comment, so root = that comment id. Otherwise fetch the thread and take its first-level comment id as the root. Send both ids explicitly, and treat "cannot determine root" as a hard stop rather than guessing and shipping a misplaced comment.

## Verification

With the root passed explicitly the reply was accepted (HTTP 200, cid returned) and the response echoed server_reply_id equal to the intended root, and the client reported the reply target as the top-level comment. Two real replies to @-mentions were delivered this way without producing stray top-level comments.
