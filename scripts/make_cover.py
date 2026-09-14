# -*- coding: utf-8 -*-
"""作品封面生成器 v2（1920×1080，表单要求的 16:9 横版）。

v2 变更：删除底部小字数据条；画风升级——深色渐变底、双色光晕、
渐变主标题、中央极简符号（大脑-节点隐喻）、悬浮卡片徽章。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parents[1]
W, H = 1920, 1080


def F(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    name = "msyhbd.ttc" if bold else "msyh.ttc"
    return ImageFont.truetype(r"C:\Windows\Fonts\{}".format(name), size)


def vertical_gradient(w: int, h: int, top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        img.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img.resize((w, h))


def add_glow(base: Image.Image, cx: int, cy: int, r: int, color: tuple, alpha: float) -> None:
    overlay = Image.new("RGB", base.size, color)
    mask = Image.new("L", base.size, 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([cx - r, cy - r, cx + r, cy + r], fill=int(alpha * 255))
    mask = mask.filter(ImageFilter.GaussianBlur(radius=r // 3))
    base.paste(overlay, (0, 0), mask)


def main() -> int:
    # 1. 渐变底 + 双色光晕
    img = vertical_gradient(W, H, (8, 15, 35), (22, 33, 62))
    add_glow(img, 380, 300, 430, (10, 120, 110), alpha=0.5)   # 左青
    add_glow(img, 1540, 800, 450, (70, 40, 110), alpha=0.5)   # 右紫
    d = ImageDraw.Draw(img)

    # 2. 中央极简符号（大脑-节点隐喻）
    cx, cy = W // 2, 200
    d.ellipse([cx - 56, cy - 56, cx + 56, cy + 56], outline=(94, 234, 212), width=6)
    d.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=(94, 234, 212))
    for deg in range(0, 360, 60):
        a = math.radians(deg)
        px, py = cx + math.cos(a) * 150, cy + math.sin(a) * 150
        d.line([cx + math.cos(a) * 56, cy + math.sin(a) * 56, px, py],
               fill=(94, 234, 212), width=3)
        d.ellipse([px - 9, py - 9, px + 9, py + 9], outline=(148, 163, 184), width=2)

    # 3. 主标题（渐变色：先画到临时渐变图上再用文字遮罩合成）
    title = "学习副驾 Study Copilot"
    font_title = F(True, 104)
    tw = d.textlength(title, font=font_title)
    tx, ty = int((W - tw) / 2), 380
    grad = vertical_gradient(W, H, (94, 234, 212), (59, 130, 246))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).text((tx, ty), title, font=font_title, fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)  # 重新绑定

    # 4. 副标题
    tagline = "把学习大脑，装进任何 AI Agent"
    tw2 = d.textlength(tagline, font=F(False, 44))
    d.text(((W - tw2) / 2, 570), tagline, font=F(False, 44), fill=(226, 232, 240))

    # 5. 三徽章（悬浮卡片）
    badges = [("任何 Agent", "Codex · Claude Code · 通用"),
              ("任何科目", "考研 · 法考 · CPA · 更多"),
              ("端云协同", "本地检索 × 云端 Qwen")]
    bw, bh, gap = 480, 150, 40
    x0 = (W - (bw * 3 + gap * 2)) // 2
    for i, (title_b, desc) in enumerate(badges):
        x = x0 + i * (bw + gap)
        y = 720
        border = (94, 234, 212) if i == 2 else (51, 65, 85)
        d.rounded_rectangle([x, y, x + bw, y + bh], 20, fill=(30, 41, 59),
                            outline=border, width=3)
        d.text((x + 40, y + 30), title_b, font=F(True, 42), fill=(94, 234, 212))
        d.text((x + 40, y + 90), desc, font=F(False, 26), fill=(148, 163, 184))

    # 6. 顶部品牌行
    d.ellipse([80, 70, 116, 106], fill=(94, 234, 212))
    d.text((136, 66), "开源 MIT · 天猫AI黑客松参赛作品", font=F(False, 30), fill=(148, 163, 184))

    # 7. v2：底部小字数据条已删除——留白聚焦
    img.save(REPO / "封面.png")
    print("封面 v2 已生成：", REPO / "封面.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
