---
title: "Roleplay Vocative vs Mention — Entity Disambiguation Failure in Portuguese Turn Routing"
domain: "agent"
tags:
  - roleplay
  - entity-disambiguation
  - vocative
  - turn-routing
  - portuguese
  - go
  - dialogue-systems
status: "published"
evidence_level: "E2"
created: "2026-09-11"
updated: "2026-09-11"
source: "issue-1630"
provenance:
  source: "dsh"
  contributor: "Ikalus1988"
  evidence: "locally reproduced + unit tested"
---

# Roleplay Vocative vs Mention — Entity Disambiguation Failure in Portuguese Turn Routing

## Problem

In a Go roleplay chat app, a user wrote:

```
Arlete, vá até a loja da Ana
```

(`Arlete` = main character/protagonist, `Ana` = NPC auto-created by NPC extraction.)

The next reply showed the protagonist's own line labeled as the NPC:

```
Ana: certo, estou indo
```

The main character "spoke as" the NPC — the protagonist's 1st-person utterance was rendered with the NPC's name as speaker.

The same defect affects any sentence where an NPC name appears as the object of a preposition (e.g. "da Ana", "com o Pedro") or inside a descriptive clause, not as a vocative address.

## Root Cause

The turn router's `resolveSpeaker` function uses a word-boundary match of any registered NPC name in the user text as the turn speaker. The logic conflates two distinct linguistic phenomena:

1. **Vocative address** — the user is directly addressing a character: `"Ana, você viu a Arlete?"`
2. **Mention** — the user is talking *about* a character: `"vá até a loja da Ana"`

Because `mention == address` in the code, a bare mention of "Ana" as the object of a preposition ("na loja da Ana") selects Ana as the turn speaker. The turn speaker is then used as the default "speaker" stamped on every JSON block that has an empty speaker field, so the protagonist's unlabeled 1st-person block was rendered with the NPC's name.

A secondary defect: the deterministic "fast nominal secondary speaker" helper has the same flaw — a name at end-of-text counted as a vocative even when preceded by a preposition.

Additionally, the presence gate was fail-open: an NPC name that does not resolve in the registry could still become the turn speaker.

## Solution

Separate **MENTION** from **VOCATIVE ADDRESS** in the turn router.

### 1. Strict vocative detector

A name is a vocative (direct address) only when:

| Pattern | Example | Vocative? |
|---------|---------|-----------|
| Name at utterance start + `,` `:` `;` `!` `?` | `"Ana, vem aqui"` | Yes |
| Name wrapped in markdown/quotes | `"\"Ana\" diz que sim"` | Yes |
| Name preceded by `,` or `—` + followed by punctuation/space/end | `"eu vi, Ana, ontem"` | Yes |
| Name preceded by a preposition (`da`, `do`, `com`, `para`, `na`, etc.) | `"vá até a loja da Ana"` | **No** |
| Name in mid-sentence without punctuation frame | `"encontrei a Ana ontem"` | **No** |

```go
// isVocative returns true if name appears as a direct address in utterance.
// A name preceded by a preposition (da, do, com, para, na, etc.) is NOT a vocative.
func isVocative(utterance, name string) bool {
    // Preposition check: if name is preceded by "preposition + space", it's a mention, not address
    prepositions := []string{"da ", "do ", "de ", "com ", "para ", "na ", "no ", "em ", "a ", "o "}
    for _, prep := range prepositions {
        idx := strings.Index(utterance, prep+name)
        if idx >= 0 {
            return false
        }
    }
    // Start-of-utterance + punctuation
    if strings.HasPrefix(utterance, name) {
        rest := strings.TrimPrefix(utterance, name)
        if len(rest) > 0 && (rest[0] == ',' || rest[0] == ':' || rest[0] == ';' || rest[0] == '!' || rest[0] == '?') {
            return true
        }
    }
    // Surrounded by punctuation / markdown
    for _, frame := range []string{`, ` + name + `,`, `"` + name + `"`, `" ` + name + `"`, "` + name + "`"} {
        if strings.Contains(utterance, frame) {
            return true
        }
    }
    return false
}
```

### 2. Explicit vocative wins over NPC mention

In `resolveSpeaker`, if the protagonist is explicitly addressed by vocative, return `""` (protagonist) deterministically — do not call the LLM classifier:

```go
func resolveSpeaker(utterance, protagonist string, npcs map[string]NPC) string {
    // (1) Protagonist vocative wins deterministically
    if isVocative(utterance, protagonist) {
        return ""
    }
    // (2) NPC vocative (strict)
    for name := range npcs {
        if isVocative(utterance, name) {
            return name
        }
    }
    // (3) No vocative found — protagonist speaks (mentions don't select speaker)
    return ""
}
```

### 3. Reuse strict detector in fast secondary-speaker path

The deterministic "fast nominal secondary speaker" helper must use the same `isVocative` check. A name at end-of-text preceded by a preposition (`"da Ana"`) must NOT count as a vocative.

### 4. Close fail-open presence gate

An NPC name that does not resolve in the NPC registry must not become the turn speaker. Return `""` (protagonist) for unregistered names.

## Verification

Table-driven unit tests for the vocative detector:

| Input | Expected |
|-------|----------|
| `"Arlete, vá até a loja da Ana"` | vocative(Arlete)=true, vocative(Ana)=false |
| `"Ana:"` | vocative(Ana)=true |
| `"Ana, vem aqui"` | vocative(Ana)=true |
| `"vá até a loja da Ana"` | vocative(Ana)=false |
| `"encontrei a Ana ontem"` | vocative(Ana)=false |
| `"Ana foi à loja"` | vocative(Ana)=false |

Service-level tests:

- `resolveSpeaker("Arlete, vá até a loja da Ana", "Arlete", {Ana: NPC})` → `""` (protagonist), even with Ana registered AND marked present.
- `resolveSpeaker("Ana, você viu a Arlete?", "Arlete", {Ana: NPC})` → `"Ana"` (Ana is vocatively addressed).
- Unknown/absent NPC name never becomes turn speaker.

Full repo test suite and `golangci-lint` pass.

## Related

- Issue [#1547](https://github.com/Ikalus1988/MisakaNet/issues/1547) — Prevenção de Loops de Diálogo e Envenenamento de Contexto no Llama 3.3 (dialogue loop prevention and context poisoning; this lesson covers the entity-disambiguation facet of the same class of failures).
- Issue [#1396](https://github.com/Ikalus1988/MisakaNet/issues/1396) — personagens entram em conflito repetitivo (repetitive character conflict; related to the same entity-binding problem in Portuguese roleplay).
- `lessons/contrib/agent-roleplay-time-consistency-hallucination.md` — time consistency hallucinations in roleplay agents (different failure class, same domain).
