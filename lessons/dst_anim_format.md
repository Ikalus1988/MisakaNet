# DST (Don't Starve Together) Animation Format Analysis

## Overview
This lesson documents the reverse-engineered structure of `anim.bin` and `build.bin` files found in DST `anim/*.zip` archives.

## anim.bin Structure
The `anim.bin` file (identified by `ANIM` magic) contains frame data following the animation name strings.

### Frame Data Analysis
- **Frame Size:** Observed 273B (idle/cooked) to 281B (idle_planted).
- **Static Blocks:** 64-byte identical blocks found at offsets 96, 160, and 224 within the frame region.
- **Dynamic Data:** The first 64 bytes vary per frame, likely representing transformation matrices or vertex offsets.

## build.bin Structure
The `build.bin` file (identified by `BILD` magic) defines the per-frame transform layout. Current research suggests a hierarchical structure mapping symbols to texture atlas coordinates.

## Implementation Notes
When parsing these files, ensure to:
1. Validate the `ANIM` or `BILD` magic bytes.
2. Skip the string table before reading frame blocks.
3. Treat the 64-byte static blocks as padding or metadata headers for the subsequent transform data.
