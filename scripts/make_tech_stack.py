# -*- coding: utf-8 -*-
"""技术栈全景图生成器（1920×1080，与封面 v2 同品牌风格）。

分层结构：宿主适配层 → Skills 核心 → 端侧 AI PC ⇄ 云端 Qwen → 质量工程。
数字均取真值：36 次调用留痕、97 tests、15 Skill × 23 契约（check_numbers 口径）。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parents[1]
W, H = 1920, 1080

CYAN = (94, 234, 212)
BLUE = (59, 130, 246)
PURPLE = (167, 139, 250)
INDIGO = (129, 140, 248)
SLATE = (148, 163, 184)
LIGHT = (226, 232, 240)
CARD = (30, 41, 59)
CARD_DARK = (20, 30, 50)
EDGE = (51, 65, 85)


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


def varrow(d: ImageDraw.ImageDraw, x: int, y1: int, y2: int, color: tuple, w: int = 4) -> None:
    """竖直向下箭头（y1 → y2，y2 > y1）。"""
    d.line([x, y1, x, y2 - 14], fill=color, width=w)
    d.polygon([(x - 11, y2 - 16), (x + 11, y2 - 16), (x, y2)], fill=color)


def centered(d: ImageDraw.ImageDraw, cx: int, y: int, text: str, font, fill) -> None:
    d.text((cx - d.textlength(text, font=font) / 2, y), text, font=font, fill=fill)


def chip_row(d: ImageDraw.ImageDraw, cx: int, y: int, texts: list[str], color: tuple) -> None:
    """居中排布一排圆角芯片。"""
    font = F(True, 24)
    widths = [d.textlength(t, font=font) + 64 for t in texts]
    gap = 28
    x = cx - (sum(widths) + gap * (len(texts) - 1)) / 2
    for t, w in zip(texts, widths):
        d.rounded_rectangle([x, y, x + w, y + 46], 23, outline=color, width=2)
        centered(d, x + w / 2, y + 8, t, font, LIGHT)
        x += w + gap


def main() -> int:
    img = vertical_gradient(W, H, (8, 15, 35), (22, 33, 62))
    add_glow(img, 400, 620, 380, (10, 120, 110), alpha=0.42)   # 左青（端侧）
    add_glow(img, 1520, 520, 400, (70, 40, 110), alpha=0.42)   # 右紫（云端）
    d = ImageDraw.Draw(img)

    # ── 标题区 ─────────────────────────────────────────────
    centered(d, W // 2, 44, "学习副驾 · 技术栈全景", F(True, 62), LIGHT)
    centered(d, W // 2, 124, "Study Copilot · 端云协同 × 任何 Agent × 任何科目", F(False, 28), SLATE)

    # ── 第一层：宿主适配 ───────────────────────────────────
    d.rounded_rectangle([140, 178, 1780, 300], 18, fill=CARD, outline=EDGE, width=2)
    d.text((180, 192), "宿主适配层", font=F(True, 32), fill=CYAN)
    note = "多宿主安装 · 清单化卸载"
    d.text((1740 - d.textlength(note, font=F(False, 22)), 200), note, font=F(False, 22), fill=SLATE)
    chip_row(d, W // 2, 246, ["Codex", "Claude Code", "通用 Agent"], INDIGO)
    varrow(d, W // 2, 300, 340, INDIGO)

    # ── 第二层：Skills 核心 ────────────────────────────────
    d.rounded_rectangle([140, 340, 1780, 436], 18, fill=CARD_DARK, outline=EDGE, width=2)
    centered(d, W // 2, 356, "Skills 核心 · 15 Skill × 23 行为契约", F(True, 34), LIGHT)
    centered(d, W // 2, 402, "Markdown 契约 + JSON Schema 严格校验 · 无后台服务 · 配置驱动任意科目",
             F(False, 24), SLATE)
    varrow(d, 510, 436, 478, CYAN)
    varrow(d, 1410, 436, 478, PURPLE)

    # ── 第三层左：端侧 AI PC ───────────────────────────────
    d.rounded_rectangle([140, 478, 880, 848], 22, fill=CARD, outline=CYAN, width=4)
    d.text((180, 500), "端侧 · 本地 AI PC", font=F(True, 36), fill=CYAN)
    tag = "数据不出域"
    d.text((850 - d.textlength(tag, font=F(False, 22)), 512), tag, font=F(False, 22), fill=SLATE)
    d.line([180, 560, 840, 560], fill=EDGE, width=2)
    edge_items = [
        "bge-small-zh-v1.5 embedding（ONNX · CPU）",
        "512 维语义索引 / 毫秒级召回",
        "npz 向量缓存 + 增量索引（19× 加速）",
        "FSRS 间隔复习调度",
        "Obsidian Vault 本地记忆",
    ]
    y = 582
    for it in edge_items:
        d.text((184, y), "▪", font=F(True, 26), fill=CYAN)
        d.text((224, y), it, font=F(False, 27), fill=LIGHT)
        y += 50

    # ── 第三层右：云端 Qwen ────────────────────────────────
    d.rounded_rectangle([1040, 478, 1780, 848], 22, fill=CARD, outline=PURPLE, width=4)
    d.text((1080, 500), "云端 · 千问 Qwen", font=F(True, 36), fill=PURPLE)
    tag2 = "百炼 DashScope"
    d.text((1745 - d.textlength(tag2, font=F(False, 22)), 512), tag2, font=F(False, 22), fill=SLATE)
    d.line([1080, 560, 1740, 560], fill=EDGE, width=2)
    cloud_items = [
        "qwen-flash / qwen3.8-flash",
        "错因定向 · 原创变式题 + 二次精讲",
        "任意科目配置包生成（法考 / 注会实证）",
        "36 次真实调用全留痕（token / 时延）",
        "防泄漏断言 + --stats 聚合审计",
    ]
    y = 582
    for it in cloud_items:
        d.text((1084, y), "▪", font=F(True, 26), fill=PURPLE)
        d.text((1124, y), it, font=F(False, 27), fill=LIGHT)
        y += 50

    # ── 端 ⇄ 云 协同连接 ───────────────────────────────────
    centered(d, 960, 616, "协同", F(True, 36), LIGHT)
    ay = 690
    d.line([892, ay, 1028, ay], fill=INDIGO, width=5)
    d.polygon([(888, ay), (916, ay - 12), (916, ay + 12)], fill=CYAN)
    d.polygon([(1032, ay), (1004, ay - 12), (1004, ay + 12)], fill=PURPLE)
    centered(d, 960, 726, "最小交接", F(False, 20), SLATE)
    centered(d, 960, 752, "互为降级", F(False, 20), SLATE)

    # ── 第四层：质量工程 ───────────────────────────────────
    varrow(d, 510, 848, 890, CYAN)
    varrow(d, 1410, 848, 890, PURPLE)
    d.rounded_rectangle([140, 890, 1780, 1006], 18, fill=CARD, outline=EDGE, width=2)
    centered(d, W // 2, 906, "质量工程 · 六道 CI 门禁 × Python 3.10-3.12 矩阵", F(True, 32), LIGHT)
    centered(d, W // 2, 952, "97 tests · Schema 校验 · 文档路径 · semgrep 安全 · 契约覆盖 · 数字一致性",
             F(False, 24), SLATE)

    # ── 页脚 ───────────────────────────────────────────────
    centered(d, W // 2, 1030,
             "技术栈继承并演进自前作 408 考研插件 v2.4.0（Skills-only · 行为契约 · Vault 记忆） · MIT 开源 · github.com/yq6666-66/study-copilot-skills",
             F(False, 22), SLATE)

    out = REPO / "docs" / "competition" / "技术栈图.png"
    img.save(out)
    print("技术栈图已生成：", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
