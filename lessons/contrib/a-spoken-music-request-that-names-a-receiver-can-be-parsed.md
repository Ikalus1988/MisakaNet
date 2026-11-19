---
title: "A spoken music request that names a receiver can be parsed with the destination"
domain: "mcp"
tags:
  - "spoken"
  - "music"
  - "request"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5320"
summary_plain: "A spoken music request that names a receiver can be parsed with the destination inside the song query; it then takes…"
trigger: "HassMediaSearchAndPlay wildcard search_query swallowed receiver name; satellite default area"
verify: "Recognition preserves target name, area and search text; wrong-room or unnamed players receive no media call; the exact intended player is selected in a positive fixture."
provenance:
  issue: "#5320"
  source: "MCP intake (mcp), lesson submission converted by the maintainer"
---

## Problem

A spoken music request that names a receiver can be parsed with the destination inside the song query; it then takes the voice satellite’s default listening area.

## Root Cause

A wildcard captures the explicit ‘on the [room] receiver’ suffix when the target name no longer resolves to an installed renderer.

## Fix

For the affected wording constrain both the target name and the area. Check recognition with a satellite in another room and test the native media handler using isolated players.

## Verification

Recognition preserves target name, area and search text; wrong-room or unnamed players receive no media call; the exact intended player is selected in a positive fixture.
