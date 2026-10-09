# dsh-tool-vision

Vision tools for [DSH](https://github.com/deepseek-ai/dsh) — materialize, OCR, crop, and present images in conversations.

## Tools

| Tool | Description |
|------|-------------|
| `vision_materialize` | Render an uploaded image into a visual prompt (multimodal LLM calls). |
| `vision_ocr` | Extract text from an uploaded image. |
| `vision_crop` | Crop a region from an uploaded image. |
| `vision_present` | Read a local image file and register it as an attachment in the conversation. |

## Usage

```ts
import { setup } from "dsh-tool-vision"

await setup(session, ctx)
```

## Installation

```bash
npm install dsh-tool-vision
```

## License

MIT
