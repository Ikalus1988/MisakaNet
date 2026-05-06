#!/usr/bin/env python3
"""
misakanet-avatar.py — 御坂网络像素头像生成器

根据序号生成御坂妹风格像素头像。
每个头像共享同一张脸，领巾颜色和序号不同。

用法:
  python3 misakanet-avatar.py 10032            # 生成 Misaka10032.png
  python3 misakanet-avatar.py 10032 --output ~/avatar.png
  python3 misakanet-avatar.py 10000 10005      # 批量生成 10000-10005
"""

import hashlib
import sys
import os
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("请安装 Pillow: pip install Pillow")
    sys.exit(1)


# ── 调色板 ──────────────────────────────────
# 御坂妹妹的统一配色 + 可替换的领巾色
PALETTE = {
    "skin":       (255, 219, 189),   # 肤色
    "skin_shade": (242, 198, 168),   # 肤色阴影
    "hair_dark":  (101, 67, 33),     # 深棕发
    "hair_light": (150, 110, 70),    # 浅棕发
    "eye":        (80, 60, 55),      # 眼睛
    "eye_highlight": (200, 180, 160),# 眼睛高光
    "white":      (248, 248, 248),   # 眼白
    "mouth":      (200, 130, 120),   # 嘴
    "collar":     (60, 60, 70),      # 衣领
    "collar_light": (90, 90, 100),   # 衣领浅
    "number_bg":  (220, 220, 225),   # 号码牌背景
    "number_fg":  (40, 40, 50),      # 号码牌文字
    "bg":         (240, 240, 245),   # 背景
}

# 12种领巾色（御坂妹妹的特征色）
SCARF_COLORS = [
    (70, 130, 200),   # 0: 蓝（原版）
    (200, 80, 80),    # 1: 红
    (80, 180, 100),   # 2: 绿
    (200, 170, 50),   # 3: 黄
    (170, 100, 200),  # 4: 紫
    (230, 140, 60),   # 5: 橙
    (200, 100, 160),  # 6: 粉
    (60, 180, 190),   # 7: 青
    (150, 200, 150),  # 8: 薄荷
    (100, 150, 200),  # 9: 灰蓝
    (190, 160, 140),  # 10: 米
    (80, 80, 80),     # 11: 灰
]


# ── 像素模板 (32x32) ──────────────────────
# 每个字符代表一个颜色键
# . = bg, S = skin, s = skin_shade
# H = hair_dark, h = hair_light
# E = eye, e = eye_highlight, W = white
# M = mouth, C = collar, c = collar_light
# N = number_bg, F = number_fg
# R = scarf (会被替换为领巾色)

TEMPLATE = [
    "................................",
    "................................",
    "..........HHHHHHH..............",
    "........HHHHHHHHHH............",
    ".......HHHHHHHHHHHH...........",
    "......HHHHHHHHHHHHHH..........",
    ".....HHHHHHHHHHHHHHHH.........",
    "....HHHHHHHHHHHHHHHHHH........",
    ".....sssssHHHHHHHHsssss.......",
    "....ssssssssssssssssssss......",
    "....ssRRRRRRRsssRRRRRRsss.....",
    "....sRRRRRRRRRssRRRRRRRRs.....",
    "....sRRRRRRRRRssRRRRRRRRs.....",
    "....sRRRRRssWWsssssssRRRs.....",
    "....sRRRRsWEEWeWWEEWssRRs.....",
    "....ssRRRsWeeEeWeEeeWssss.....",
    ".....ssssWWEEeeEeeEEWWsss.....",
    "......ssssWEEEEEEEEWssss......",
    ".......sssWeeeeeeeWsss........",
    "........ssssMMMMMsssss........",
    "........sss.......ssss........",
    "........sss.......ssss........",
    ".......sss.........ssss.......",
    "......sss...........ssss......",
    ".....ccc.............ccc......",
    "....cNNN.............NNNc.....",
    "....cNNN.............NNNc.....",
    "....cccc.............cccc.....",
    ".....ccc.............ccc......",
    "......ccc...........ccc.......",
    ".......ccc.........ccc........",
    "................................",
]

# 颜色映射
CHAR_MAP = {
    ".": "bg",
    "S": "skin",
    "s": "skin_shade",
    "H": "hair_dark",
    "h": "hair_light",
    "E": "eye",
    "e": "eye_highlight",
    "W": "white",
    "M": "mouth",
    "C": "collar",
    "c": "collar_light",
    "N": "number_bg",
    "F": "number_fg",
    "R": None,  # 领巾色，运行时替换
}


def get_scarf_color(number: int) -> tuple[int, int, int]:
    """根据序号决定领巾色"""
    idx = number % len(SCARF_COLORS)
    return SCARF_COLORS[idx]


def draw_avatar(number: int, scale: int = 4) -> Image.Image:
    """绘制 32x32 像素头像，按 scale 放大"""
    size = 32
    img = Image.new("RGB", (size, size))
    pixels = img.load()

    scarf_color = get_scarf_color(number)
    palette = {**PALETTE, "scarf": scarf_color}

    for y, row in enumerate(TEMPLATE):
        for x, ch in enumerate(row):
            key = CHAR_MAP.get(ch)
            if key is None and ch == "R":
                key = "scarf"
            if key is None:
                color = palette["bg"]
            else:
                color = palette.get(key, palette["bg"])
            pixels[x, y] = color

    # 放大
    if scale > 1:
        img = img.resize((size * scale, size * scale), Image.NEAREST)

    # 叠加序号文字
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)

    number_text = f"#{number}"
    font_size = max(8, scale * 3)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

    # 文字位置：底部居中
    bbox = draw.textbbox((0, 0), number_text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (img.width - tw) // 2
    ty = img.height - th - 4 * scale

    # 文字阴影
    draw.text((tx + 1, ty + 1), number_text, fill=(0, 0, 0, 180), font=font)
    # 文字主体
    draw.text((tx, ty), number_text, fill=(255, 255, 255), font=font)

    return img


def save_avatar(number: int, output_dir: str | Path) -> Path:
    """生成并保存头像"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    img = draw_avatar(number, scale=4)
    path = output_dir / f"Misaka{number:05d}.png"
    img.save(path)
    return path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    output_dir = os.environ.get("AVATAR_DIR", "avatars")
    
    # 解析参数
    args = sys.argv[1:]
    output_dir = "avatars"
    
    i = 0
    while i < len(args):
        if args[i] == "--output" and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
        else:
            i += 1

    numbers = []
    for arg in args:
        if arg == "--output":
            break
        if "-" in arg:
            start, end = arg.split("-")
            numbers.extend(range(int(start), int(end) + 1))
        else:
            try:
                numbers.append(int(arg))
            except ValueError:
                continue

    for n in numbers:
        path = save_avatar(n, output_dir)
        print(f"  Misaka{n:05d} → {path}")

    print(f"\n已生成 {len(numbers)} 个头像")


if __name__ == "__main__":
    main()
