---
domain: "archive"
title: "Pixel Art"
verification: "metadata-normalized"
source: "skill-pipeline"
status: "draft"
created: "2026-05-09"
---

## 背景

（此 lesson 从 skill `pixel-art` 自动提取，待补全）

## 根因

（待补充）

## 修复


# Pixel Art

Convert any image into retro pixel art, then optionally animate it into a short
MP4 or GIF with era-appropriate effects (rain, fireflies, snow, embers).

Two scripts ship with this skill:

- `scripts/pixel_art.py` — photo → pixel-art PNG (Floyd-Steinberg dithering)
- `scripts/pixel_art_video.py` — pixel-art PNG → animated MP4 (+ optional GIF)

Each is importable or runnable directly. Presets snap to hardware palettes
when you want era-accurate colors (NES, Game Boy, PICO-8, etc.), or use
adaptive N-color quantization for arcade/SNES-style looks.

## When to Use

- User wants retro pixel art from a source image
- User asks for NES / Game Boy / PICO-8 / C64 / arcade / SNES styling
- User wants a short looping animation (rain scene, night sky, snow, etc.)
- Posters, album covers, social posts, sprites, characters, avatars
- **批量生成社区头像**: 对同一张源图做像素化 + 颜色滤镜 + 编号叠加 — 见 `references/avatar-generation-workflow.md`

## Workflow

Before generating, confirm the style with the user. Different presets produce
very different outputs and regenerating is costly.

### Step 1 — Offer a style

Call `clarify` with 4 representative presets. Pick the set based on what the
user asked for — don't just dump all 14.

Default menu when the user's intent is unclear:

```python
clarify(
    question="Which pixel-art style do you want?",
    choices=[
        "arcade — bold, chunky 80s cabinet feel (16 colors, 8px)",
        "nes — Nintendo 8-bit hardware palette (54 colors, 8px)",
        "gameboy — 4-shade green Game Boy DMG",
        "snes — cleaner 16-bit look (32 colors, 4px)",
    ],
)
```

When the user already named an era (e.g. "80s arcade", "Gameboy"), skip
`clarify` and use the matching preset directly.

### Step 2 — Offer animation (optional)

If the user asked for a video/GIF, or the output might benefit from motion,
ask which scene:

```python
clarify(
    question="Want to animate it? Pick a scene or skip.",
    choices=[
        "night — stars + fireflies + leaves",
        "urban — rain + neon pulse",
        "snow — falling snowflakes",
        "skip — just the image",
    ],
)
```

Do NOT call `clarify` more than twice in a row. One for style, one for scene if
animation is on the table. If the user explicitly asked for a specific style
and scene in their message, skip `clarify` entirely.

### Step 3 — Generate

Run `pixel_art()` first; if animation was requested, chain into
`pixel_art_video()` on the result.

## Preset Catalog

| Preset | Era | Palette | Block | Best for |
|--------|-----|---------|-------|----------|
| `arcade` | 80s arcade | adaptive 16 | 8px | Bold posters, hero art |
| `snes` | 16-bit | adaptive 32 | 4px | Characters, detailed scenes |
| `nes` | 8-bit | NES (54) | 8px | True NES look |
| `gameboy` | DMG handheld | 4 green shades | 8px | Monochrome Game Boy |
| `gameboy_pocket` | Pocket handheld | 4 grey shades | 8px | Mono GB Pocket |
| `pico8` | PICO-8 | 16 fixed | 6px | Fantasy-console look |
| `c64` | Commodore 64 | 16 f

## 验证

（待补充）
