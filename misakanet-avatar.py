#!/usr/bin/env python3
"""
misakanet-avatar.py — 御坂网络像素头像生成器 v3

基于御坂美琴面部图像，像素化后叠加领巾色和序号。
每个头像共享同张脸，领巾色和序号不同。

用法:
  python3 misakanet-avatar.py 10032
  python3 misakanet-avatar.py 10000 10005 --output ~/avatars
"""

import sys, os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# ── 路径 ───────────────────────────────
BASE_DIR = Path(__file__).parent
BASE_FACE = BASE_DIR / "misaka-face.jpg"
PIXEL_ART_SCRIPT = BASE_DIR.parent / "creative" / "pixel-art" / "scripts" / "pixel_art.py"
if not PIXEL_ART_SCRIPT.exists():
    PIXEL_ART_SCRIPT = Path(os.environ.get("PIXEL_ART_SCRIPT", ""))
    if not PIXEL_ART_SCRIPT.exists():
        PIXEL_ART_SCRIPT = None

# ── 领巾色（12 色，御坂妹妹特征） ──────
SCARF_COLORS = [
    (70,  130, 210),  # 0: 蓝（原版）
    (210, 80,  80),   # 1: 红
    (85,  185, 105),  # 2: 绿
    (215, 180, 45),   # 3: 黄
    (175, 100, 210),  # 4: 紫
    (235, 145, 55),   # 5: 橙
    (215, 100, 165),  # 6: 粉
    (60,  185, 195),  # 7: 青
    (155, 205, 155),  # 8: 薄荷
    (100, 150, 205),  # 9: 灰蓝
    (195, 160, 140),  # 10: 米
    (80,  80,  90),   # 11: 灰
]

NUM_BG = (240, 240, 245)
NUM_BORDER = (180, 180, 185)
NUM_FG = (40, 40, 50)


def scarf_color(num):
    return SCARF_COLORS[num % len(SCARF_COLORS)]


def tint_image(img, color, intensity=0.15):
    """给图像叠加颜色滤镜"""
    overlay = Image.new("RGB", img.size, color)
    return Image.blend(img, overlay, intensity)


def pixelate(img, block=6):
    """像素化图像"""
    w, h = img.size
    small = img.resize((max(1, w // block), max(1, h // block)), Image.LANCZOS)
    return small.resize((w, h), Image.NEAREST)


def generate_avatar(number, size=128, block=6):
    """生成完整头像"""
    # 1. 加载面部
    if not BASE_FACE.exists():
        raise FileNotFoundError(f"面部图像不存在: {BASE_FACE}")
    
    img = Image.open(BASE_FACE).convert("RGB")
    
    # 2. 调整到合适尺寸（200x200 → 大小统一的输入）
    img = img.resize((200, 200), Image.LANCZOS)
    
    # 3. 像素化
    img = pixelate(img, block=block)
    
    # 4. 叠加领巾色
    tint_color = scarf_color(number)
    img = tint_image(img, tint_color, intensity=0.12)
    
    # 5. 调整到目标尺寸
    img = img.resize((size, size), Image.NEAREST)
    
    # 6. 叠加序号
    draw = ImageDraw.Draw(img)
    
    text = f"#{number}"
    
    # 找字体
    font = None
    for fp in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        if os.path.exists(fp):
            font = ImageFont.truetype(fp, size=max(10, size // 10))
            break
    if font is None:
        font = ImageFont.load_default()
    
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    # 号码牌
    px, py = (size - tw - 12) // 2, size - th - 8
    draw.rounded_rectangle(
        [px-2, py-1, px+tw+2, py+th+1],
        radius=2, fill=NUM_BG, outline=NUM_BORDER
    )
    
    # 文字阴影 + 本体
    draw.text((px+1, py+1), text, fill=(0, 0, 0), font=font)
    draw.text((px, py), text, fill=NUM_FG, font=font)
    
    return img


def save_avatar(number, output_dir="avatars"):
    path = Path(output_dir) / f"Misaka{number:05d}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    
    img = generate_avatar(number, size=128)
    img.save(path)
    return path


def main():
    if len(sys.argv) < 2:
        print("用法: python3 misakanet-avatar.py 10032 [--output dir]")
        sys.exit(1)
    
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
            a, b = arg.split("-")
            numbers.extend(range(int(a), int(b) + 1))
        else:
            try:
                numbers.append(int(arg))
            except ValueError:
                continue
    
    for n in numbers:
        p = save_avatar(n, output_dir)
        print(f"  Misaka{n:05d} → {p}")
    print(f"\n已生成 {len(numbers)} 个头像")


if __name__ == "__main__":
    main()
