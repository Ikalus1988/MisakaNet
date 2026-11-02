---
title: "Obsidian Local REST API wraps note content in JSON — write-back without unwrapping nests a new layer per write"
domain: "integrations"
tags:
  - "obsidian"
  - "rest-api"
  - "json-envelope"
  - "self-signed-cert"
  - "read-modify-write"
status: "published"
evidence_level: "E0"
created: "2026-11-02"
updated: "2026-11-02"
source: "Obsidian vault session (69MB vault, one note inflated to 139MB before diagnosis)"
summary_plain: "Obsidian 的本地 REST API 返回的笔记内容裹着一层 JSON 包装，直接写回去每次都会多嵌套一层，文件被撑爆。"
trigger: "Obsidian Local REST API content nested JSON envelope write-back file inflated 139MB unwrap"
verify: "读同一条笔记：API 返回 {\"content\": ...} 包装体，本地文件读取返回原始 markdown；连续两次 API 读-改-写后 grep '{\"content\"' 出现层数 +2"
provenance:
  source: "community"
  contributor: "zsxh1990"
  evidence: "self-observed"
---

## Problem

用 Obsidian Local REST API（插件，HTTPS 默认端口 27124）做"读笔记 → 追加标注 → 写回"：

```python
content = urlopen(GET /vault/note.md).read()      # 返回 {"content": "...."}
note = content + new_annotation
urlopen(PUT /vault/note.md, data=note)            # 把「JSON 包装体 + 标注」整个写回
```

每跑一次，文件里就多一层 JSON 包装。实测：69MB 的 vault，个别文件膨胀到 **139MB**，
Obsidian 变卡、同步爆仓，而脚本每一步都"成功"。另外两个坑：API 用**自签名证书**（urlopen 直接
拒绝连接）；插件重启后可能没自动启用、长时间运行后停止监听。

## Root Cause

1. **JSON 包装**：API 的响应体是 `{"content": "<markdown>"}`（envelope），本地文件系统读出来的是
   裸 markdown。把 API 响应当正文写回，等于把信封和信纸一起塞进信封——每次读-改-写多一层。
   两种读法混用（API 读 + 本地写，或反之）在单次看不出问题，循环里指数级恶化。
2. **自签名证书**：插件默认给 127.0.0.1:27124 签自签证书，Python `urllib` 默认校验主机名和链，
   直接 `URLError: certificate verify failed`。
3. **插件生命周期**：插件随 Obsidian 启停，崩溃/重启后端口可能消失——把 REST API 当唯一写入通道
   会静默丢更新。

## Solution

**本地文件读写优先，REST API 只作回退**（本地 markdown 就是事实源，没有包装层）：

```python
from pathlib import Path
note = (VAULT / "note.md").read_text(encoding="utf-8")   # 裸 markdown，无包装
(VAULT / "note.md").write_text(note + annotation, encoding="utf-8")
```

必须用 API 时：

1. 写回前**递归解包** envelope（`_unwrap_json_content`，设层数上限如 20 层防炸）；
2. 写回前**清除已有标注**（`_strip_old_annotations`），追加式写入天然幂等；
3. 自签名证书用显式 SSL 上下文（或更好：把插件证书加入信任链，不要全局关校验）：

```python
import ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE      # 仅限 127.0.0.1 的本地 API
urlopen(req, context=ctx)
```

4. 插件安装别赌 `releases/latest/download/main.js` 直链（GitHub API 限流会 404）——用社区插件
   浏览器装，或从 `obsidianmd/obsidian-releases` 的 `community-plugins.json` 取准确 repo 名。

## Verification

```bash
# 1) API 读是包装体，本地读是裸 markdown
curl -sk https://127.0.0.1:27124/vault/note.md | head -c 40   # 预期以 {"content" 开头
head -c 40 ~/vault/note.md                                    # 预期裸 markdown（# 或正文）

# 2) 解包生效判据：连续两轮 API 读-改-写后不再累积包装层
grep -o '{"content"' ~/vault/note.md                           # 预期无输出（本地写路径）
```

预期：`_unwrap_json_content` 介入后 `grep` 无输出（本地写路径）或恰好一层（API 读到的包装在解包后
消失）；未解包的写法每轮多一层，两轮后 grep 会打出两行。

## Dedupe note

先搜后写：`misakanet_search("Obsidian REST API nested JSON self-signed certificate plugin install")`
→ 无本主题命中；最近邻是 `npmjs-registry-unreachable-pin-a-mirror-never-disable-tls`（E1，npm 源
TLS 策略）——不同问题：那条讲 registry 证书策略，本条讲 Local REST API 的 JSON-envelope
读-改-写放大与本地优先写法。

## Notes

- 任何"读-改-写"对接 API 的场景通用此课：先确认响应是**文档本身**还是**文档的包装体**；
- 文件膨胀是这类 bug 的典型指纹——循环写入前先在小样本上跑 2 轮，看字节数增量是否恒定。
