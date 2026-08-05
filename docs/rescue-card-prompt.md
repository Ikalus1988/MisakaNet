# 急救卡图片生成 Prompt

## 通用模板

```
A vertical mobile-friendly card (1080x1920px), dark background (#0d1117), clean modern design.

Top section:
- Large bold title in white: "压缩包打不开？"
- Subtitle in gray: "先别急，试这 3 步"

Middle section - 3 numbered steps:
1. 把文件移到桌面（icon: folder-move）
2. 换 7-Zip 打开（icon: archive）
3. 重新下载一次（icon: download）

Each step has a colored number circle (blue #58a6ff), bold step title, and one-line explanation in gray.

Bottom section:
- "还不行？发截图就行" in yellow accent
- 3 items: 报错截图 / 文件后缀 / Windows 还是 Mac

Footer:
- MisakaNet logo text in blue
- "急救卡 #001" in small gray
- QR code placeholder (bottom right)
- GitHub link: github.com/Ikalus1988/MisakaNet

Style: GitHub dark theme, monospace accents, minimal, no decorative elements. Similar to a terminal/developer card but readable for non-technical users.
```

---

## 压缩包急救卡 #001

```
Vertical card (1080x1920), dark bg #0d1117.

Title: "压缩包打不开？" (white, bold, 48px)
Subtitle: "先别急，试这 3 步" (gray #8b949e, 24px)

Step 1: Blue circle "1" → "移到桌面" → "路径太长会出问题" (gray)
Step 2: Blue circle "2" → "换 7-Zip" → "系统自带的不够用" (gray)
Step 3: Blue circle "3" → "重新下载" → "可能下载不完整" (gray)

Divider line.

Yellow text: "还不行？发这 3 样就行"
- 报错截图
- 文件后缀 (.zip/.rar/.7z)
- Windows 还是 Mac

Footer:
- "MisakaNet 急救卡 #001" (small, gray)
- "不会 GitHub 没关系，发截图也算贡献" (small, blue)
- github.com/Ikalus1988/MisakaNet
```

---

## FANUC 备份急救卡 #002

```
Vertical card (1080x1920), dark bg #0d1117.

Title: "FANUC 备份打不开？" (white, bold, 48px)
Subtitle: "先别急，试这 3 步" (gray, 24px)

Step 1: Blue circle "1" → "确认有 kconvars.exe" → "FANUC备份是二进制格式" (gray)
Step 2: Blue circle "2" → "检查 robot.ini" → "需要在同目录或父目录" (gray)
Step 3: Blue circle "3" → "移到纯英文路径" → "中文路径会导致崩溃" (gray)

Divider line.

Table (2 columns, 4 rows):
| 你要找的 | 在哪个文件 |
| 负载配置 | SYSVARS.SV |
| 电极磨损 | sysspot.sv |
| 安全配置 | diocfgsv.sv |
| IO信号 | diocfgsv.sv |

Footer:
- "MisakaNet 急救卡 #002" (small, gray)
- "来自同事的 Claude 记忆包" (small, cyan)
- github.com/Ikalus1988/MisakaNet
```

---

## 朋友圈/群聊转发文案

### 压缩包 #001

```
给不会折腾压缩包的朋友做了一张"急救卡"。

3 步就能解决大部分问题：
1. 移到桌面
2. 换 7-Zip
3. 重新下载

不会描述问题也没关系，发截图就行。

来自 MisakaNet 失败经验网络。
仓库：https://github.com/Ikalus1988/MisakaNet
```

### FANUC #002

```
给搞 FANUC 机器人的同事做了一张"备份急救卡"。

备份文件打不开？3 步排查：
1. 确认有 kconvars.exe
2. 检查 robot.ini
3. 移到纯英文路径

附带常见参数提取表（负载/磨损/安全配置/IO）。

来自 MisakaNet — 把混乱的 Agent 记忆包整理成可复用的失败经验。
仓库：https://github.com/Ikalus1988/MisakaNet
```

---

## 视觉排版规范

| 元素 | 规格 |
|---|---|
| 尺寸 | 1080 x 1920 px (9:16 竖版) |
| 背景 | #0d1117 (GitHub dark) |
| 标题 | 白色, 粗体, 48px |
| 副标题 | #8b949e, 24px |
| 步骤编号 | 蓝色圆圈 #58a6ff, 32px |
| 步骤文字 | 白色, 粗体, 28px |
| 说明文字 | #8b949e, 20px |
| 强调文字 | 黄色 #d29922 或 蓝色 #58a6ff |
| 二维码 | 右下角, 120x120px |
| 底部链接 | #8b949e, 16px |
