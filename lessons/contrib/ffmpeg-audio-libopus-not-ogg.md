---
{
  "domain": "contrib",
  "title": "ffmpeg audio libopus not ogg",
  "verification": "metadata-normalized",
  "{\"title\"": "FFmpeg 音频转码：必须用 libopus 而非 -format ogg\", \"domain\": \"audio\", \"tags\": \"\", \"source\": \"hanged-man\", \"status\": \"published\", \"created\": \"2026-03-29\", \"confidence\": \"0.9\", \"scope\": \"broad\", \"domain_expert\": \"hanged-man\", \"verified_date\": \"2026-03-29\"}",
  "created": "2026-07-06",
  "source": "unknown"
}
---

## 问题

FFmpeg 输出 OGG 文件为 0 字节。

## 根因

使用了不存在的 `-format ogg` flag。

## 错误写法

```bash
ffmpeg -i input.wav -format ogg output.ogg  # -format 不存在
```

## 正确写法

```bash
ffmpeg -i input.wav -ar 24000 -ac 1 -c:a libopus output.ogg
```
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 额外注意

- 交互式覆盖提示：先 `os.remove(out)` 删除旧文件再调用 FFmpeg
- `-y` flag 在 Windows MSYS2 构建下会失效
