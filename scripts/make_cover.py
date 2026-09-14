# -*- coding: utf-8 -*-
"""作品封面生成器（1920×1080，表单要求的 16:9 横版）。

品牌风格与演示视频一致：深色底 + 品牌青 + 四色状态点缀。
输出：封面.png（仓库根层，供活动页上传与作品包使用）。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
W, H = 1920, 1080
C_BG = (15, 23, 42)
C_PANEL = (30, 41, 59)
C_TEXT = (226, 232, 240)
C_DIM = (148, 163, 184)
C_ACCENT = (94, 234, 212)
C_YELLOW = (253, 224, 71)


def F(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    name = "msyhbd.ttc" if bold else "msyh.ttc"
    return ImageFont.truetype(r"C:\Windows\Fonts\{}".format(name), size)


def main() -> int:
    img = Image.new("RGB", (W, H), C_BG)
    d = ImageDraw.Draw(img)

    # 顶部品牌行
    d.ellipse([80, 70, 116, 106], fill=C_ACCENT)
    d.text((136, 66), "学习副驾 Study Copilot", font=F(False, 34), fill=C_TEXT)
    d.text((W - 560, 66), "天猫AI黑客松 · 高校挑战赛 参赛作品", font=F(False, 28), fill=C_DIM)

    # 主标题
    t = "装进任何 Agent 的\n学习认知引擎"
    y = 220
    for ln in t.splitlines():
        d.text((120, y), ln, font=F(True, 96), fill=C_TEXT)
        y += 130

    # 三徽章
    badges = [("任何 Agent", "Codex / Claude Code / 通用"),
              ("任何科目", "考研预置 · 法考/CPA 可扩展"),
              ("端云协同", "本地检索 × 云端 Qwen")]
    x = 120
    for title, desc in badges:
        d.rounded_rectangle([x, 620, x + 520, 800], 20, outline=C_ACCENT, width=4)
        d.text((x + 36, 650), title, font=F(True, 44), fill=C_ACCENT)
        d.text((x + 36, 720), desc, font=F(False, 26), fill=C_DIM)
        x += 560

    # 数据条（真实数字）
    stats = "15 Skills · 23 契约 · 92 tests · 38 次 Qwen 真实调用全程留痕"
    d.text(((W - d.textlength(stats, font=F(False, 30))) / 2, 880),
           stats, font=F(False, 30), fill=C_YELLOW)

    # 四色状态点（掌握度色块示意）
    for i, c in enumerate([(34, 197, 94), (245, 158, 11), (239, 68, 68), (100, 116, 139)]):
        d.ellipse([860 + i * 60, 960, 884 + i * 60, 984], fill=c)

    img.save(REPO / "封面.png")
    print("封面已生成：", REPO / "封面.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
