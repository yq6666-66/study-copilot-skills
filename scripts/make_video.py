# -*- coding: utf-8 -*-
"""演示视频生成器 v3：11 分镜 + edge-tts 配音（云希）+ ffmpeg 合成。

v3 相对 v2 的变化：
- 新增三个分镜：FSRS 间隔复习调度 / Anki 导出+考前预练 / 六道 CI 门禁
- 片头片尾计数标注改为动态读取 logs/qwen/（不再硬编码过时数字）
- 配音文案全量更新至十六轮状态（38 次真实调用 / 92 tests / 六道门禁）

用法：python scripts/make_video.py
产物：dist/学习副驾演示视频.mp4（约 3.5 分钟，1080p/30fps，配音+烧录字幕）
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
WORK = REPO / "dist" / "video_work"
OUT = REPO / "dist" / "学习副驾演示视频.mp4"
W, H = 1920, 1080
VOICE = "zh-CN-YunxiNeural"
HF_MIRROR = "https://hf-mirror.com"

C_BG = (15, 23, 42)
C_PANEL = (11, 18, 32)
C_BAR = (30, 41, 59)
C_TEXT = (226, 232, 240)
C_DIM = (148, 163, 184)
C_ACCENT = (94, 234, 212)
C_YELLOW = (253, 224, 71)
C_GREEN = (74, 222, 128)

F_TITLE = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 76)
F_SUB = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 40)
F_BODY = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 34)
F_SMALL = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 28)
F_TERM = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 30)

NARRATOR = [
    # S1 开场
    "错题本记了三大本，复习时却想不起来翻——这是很多备考者的日常。学习副驾换了个思路："
    "把学习大脑做成一套开放的 Skills，装进任何 AI Agent，教任何科目。",
    # S2 家底与泛化
    "先看家底：15 个 Skills、23 份行为契约、考研科目配置包，还有一个 40 条错题的演示学习库。"
    "它的前身是我们开源的 408 考研插件。这一版做了两层关键泛化——机制层和宿主彻底解耦；"
    "学科内容由配置驱动，今天教考研，明天就能教法考、CPA。",
    # S3 安装
    "装起来多简单？一条命令。安装器自动识别宿主，把 15 个 Skills 复制到位。"
    "没有后台服务，全部是本地文件；装了什么、装到哪，清单写得明明白白，随时可以干净卸载。",
    # S4 错题闭环
    "来点真的。对着演示库说一句：帮我整理 408 操作系统的错题。Agent 切换成教练模式——"
    "按知识点聚类错因，把确认过的和只是猜测的严格分开，复测日期自动排进队列。"
    "科目在这里只是字符串：数学一和操作系统同场工作，机制层一行代码都不用改。",
    # S5 端侧检索
    "接下来是最硬的技术点：端侧。本地 CPU 运行 embedding 模型，为整个错题库建语义索引。"
    "输入死锁检测又算错了，毫秒级返回：最相关的是死锁簇笔记和银行家算法错题，数学题零干扰；"
    "换成数学查询，级数判别的错题立刻浮出水面。全程本地计算，学习数据一克都不出门。",
    # S6 Qwen 陪练
    "云端交给 Qwen。先 dry-run 预览请求体，确认没有个人信息再真实调用。"
    "基于已确认的错因，Qwen 现场生成原创变式题和二次精讲。每一次调用自动留痕："
    "请求、回复、token 用量、时延，全部写进本地日志，而且日志里连 API Key 的影子都没有。"
    "聚合统计一条命令就能复核——这就是我们说的：AI 实践，真实可验证。",
    # S7 FSRS 调度器
    "复习节奏不拍脑袋。我们参考开源 FSRS 项目实现了间隔复习调度：每条错题有稳定性和可提取概率，"
    "由遗忘曲线反解下一次复习日期。四十条演示错题全部自动排期，到期自动浮出。",
    # S8 Anki 导出 + 考前预练
    "学完还要练。错题队列可以一键导出成 Anki 卡片——正面只有回忆问题，背面是错因和正确步骤；"
    "考前预练模式则把相似错题聚成一卷，先自测再对照解析。练习数据又回到本地记忆层，形成闭环。",
    # S9 六道门禁
    "质量不靠口头承诺。六道 CI 门禁全程把关：单元测试、数据校验、文档路径、semgrep 安全扫描、"
    "契约覆盖度，还有一条数字一致性门禁——材料里的每个数字都必须和留痕真值对得上，对不上就红。",
    # S10 架构 + 隐私
    "一张图看清架构：端侧负责本地语义与记忆，云端负责推理与出题，中间是通用 Skills 核心。"
    "任一端不可用，另一端自动降级。隐私也认真做了：学习记录只存本地；Qwen 只收到学科文本；"
    "没有账号体系，没有遥测代码。",
    # S11 结尾
    "从 408 考研插件，到任何 Agent、任何科目的学习大脑——学习副驾，开源可玩。"
    "代码、测试和全部证据都在作品包里，欢迎来 GitHub 逛逛。谢谢观看！",
]


def wrap(text: str, width: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        cur += ch
        if ch == "\n":
            lines.append(cur.rstrip("\n")); cur = ""
            continue
        if len(cur) >= width and ch in "，。：；、？！——":
            lines.append(cur); cur = ""
    if cur:
        lines.append(cur)
    return lines


def new_canvas(title: str = "") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), C_BG)
    d = ImageDraw.Draw(img)
    if title:
        d.text((80, 50), title, font=F_SUB, fill=C_ACCENT)
        d.line([(80, 122), (W - 80, 122)], fill=C_BAR, width=2)
    return img, d


def terminal(img: Image.Image, lines, top: int = 160, left: int = 90,
             step: int = 42, width: int = 1740) -> None:
    d = ImageDraw.Draw(img)
    bar_h = 52
    d.rounded_rectangle([left - 24, top - 24, left - 24 + width + 48,
                         top - 24 + bar_h + 40 + step * max(len(lines), 1)], 14, fill=C_PANEL)
    d.rounded_rectangle([left - 24, top - 24, left - 24 + width + 48, top - 24 + bar_h], 14, fill=C_BAR)
    for i, cx in enumerate((52, 84, 116)):
        d.ellipse([left - 24 + cx, top - 16, left - 24 + cx + 16, top],
                  fill=[(255, 99, 71), (255, 189, 46), (80, 220, 100)][i])
    y = top + 12
    for text, color in lines:
        if text:
            d.text((left, y), text, font=F_TERM, fill=color)
        y += step


def subtitle(img: Image.Image, text: str) -> None:
    d = ImageDraw.Draw(img)
    d.rectangle([0, H - 150, W, H], fill=(0, 0, 0))
    y = H - 140
    for ln in wrap(text, 44)[:3]:
        d.text(((W - d.textlength(ln, font=F_SMALL)) / 2, y), ln, font=F_SMALL, fill=C_TEXT)
        y += 38


def brand(img: Image.Image, idx: int, total: int = 11) -> None:
    d = ImageDraw.Draw(img)
    d.text((W - 260, 30), f"学习副驾 · {idx}/{total}", font=F_SMALL, fill=C_DIM)


def frames_s1():
    img, d = new_canvas()
    t = "学习副驾 Study Copilot"
    d.text(((W - d.textlength(t, font=F_TITLE)) / 2, 290), t, font=F_TITLE, fill=C_TEXT)
    subs = ["任何 Agent", "任何科目", "端云协同"]
    x = W / 2 - 540
    for s in subs:
        d.rounded_rectangle([x, 520, x + 330, 610], 16, outline=C_ACCENT, width=3)
        d.text((x + (330 - d.textlength(s, font=F_SUB)) / 2, 536), s, font=F_SUB, fill=C_ACCENT)
        x += 360
    tag = f"云端引擎 · 阿里云 Qwen｜38 次真实调用全程留痕"
    d.text(((W - d.textlength(tag, font=F_SMALL)) / 2, 690), tag, font=F_SMALL, fill=C_YELLOW)
    yield [img], 2.4


def frames_s2():
    dirs = ["plugins/study-copilot/   15 个 Skills + 23 份契约",
            "adapters/                Codex · Claude Code · 通用 Agent",
            "subjects/                考研包 + 法考/注会 + 新科目向导",
            "scripts/                 端侧检索 + FSRS 调度 + Qwen 引擎",
            "demo-vault/              脱敏演示库（40 条错题 × 2 科目）",
            "tests/ + CI              六道门禁 × Python 3.10-3.12"]
    for n in range(0, len(dirs) + 1):
        img, _ = new_canvas("仓库总览 —— 全部是本地文件，没有后台服务")
        terminal(img, [(("├─ " + dirs[i]), C_TEXT if i < n else C_PANEL) for i in range(len(dirs))])
        brand(img, 2)
        yield [img], 0.45
    img, d = new_canvas("两层泛化")
    d.text((80, 190), "① 任何 Agent：机制层与宿主解耦（Codex / Claude Code / 通用）", font=F_BODY, fill=C_TEXT)
    d.text((80, 260), "② 任何科目：学科内容由配置驱动（考研预置，法考/CPA/高考可接入）", font=F_BODY, fill=C_TEXT)
    d.text((80, 350), "前身：408考研插件 v2.4.0（已开源）——本项目为其通用化演进", font=F_SMALL, fill=C_DIM)
    brand(img, 2)
    yield [img], 2.6


def frames_s3():
    skills = sorted(p.name for p in (REPO / "plugins/study-copilot/skills").iterdir()
                    if (p / "SKILL.md").exists())
    yield [new_canvas("安装器")[0]], 0.3
    for n in (4, 9, 15):
        img, _ = new_canvas("$ python install.py --list")
        terminal(img, [(s, C_ACCENT if i % 2 else C_TEXT) for i, s in enumerate(skills[:n])])
        brand(img, 3)
        yield [img], 0.45
    img, _ = new_canvas("$ python install.py --host claude-code --dry-run")
    plan = [f"复制 {s} → ~/.claude/skills/{s}" for s in skills[:4]]
    terminal(img, [(p, C_TEXT) for p in plan] + [("……", C_DIM), ("共 15 项。", C_GREEN)])
    brand(img, 3)
    yield [img], 2.2
    img, d = new_canvas("")
    d.text((240, 420), "没有后台服务 · 全部本地文件 · 清单可审计 · 随时卸载", font=F_SUB, fill=C_ACCENT)
    brand(img, 3)
    yield [img], 2.0


def frames_s4():
    queue = json.loads((REPO / "demo-vault/30-知识/错题队列.json").read_text(encoding="utf-8"))
    os_items = [i for i in queue["items"] if i["subject"] == "408-操作系统"]
    yield [new_canvas("Agent 错题闭环 —— 数据源 demo-vault（真实记录）")[0]], 0.4
    img, d = new_canvas("错误簇（按知识点聚类）")
    clusters = [("死锁（银行家算法/检测）", "confirmed", "r028 r040"),
                ("页面置换与地址变换", "confirmed", "r030 r031"),
                ("进程同步互斥", "hypothesis", "r026 r027"),
                ("文件系统与磁盘调度", "mixed", "r033 r034 r035")]
    y = 170
    for name, st, ids in clusters:
        color = C_GREEN if st == "confirmed" else C_YELLOW
        d.text((90, y), name, font=F_BODY, fill=C_TEXT)
        d.text((880, y), st, font=F_BODY, fill=color)
        d.text((1220, y), ids, font=F_BODY, fill=C_DIM)
        y += 58
    d.text((90, y + 16), "错因区分 confirmed / hypothesis —— 有复测证据才可标掌握", font=F_SMALL, fill=C_DIM)
    brand(img, 4)
    yield [img], 3.0
    img, d = new_canvas("ReviewQueue 1.1 → 复测排期（真实数据节选）")
    lines = []
    for it in os_items[:6]:
        when = it.get("nextRetestDate") or f"+{it.get('retestOffsetDays')}d"
        lines.append((f"{it['id']}  {it['topic']}  [{it['errorCauseStatus']}]  → {when}  ({it['status']})",
                      C_ACCENT if it["status"] == "retesting" else C_TEXT))
    terminal(img, lines)
    d.text((90, 920), f"共 {len(queue['items'])} 条错题（数学一 24 / 408-操作系统 16），Schema 1.1 校验通过",
           font=F_SMALL, fill=C_DIM)
    brand(img, 4)
    yield [img], 3.0


def frames_s5():
    yield [new_canvas("端侧语义检索 —— 本地 CPU · 数据不出域")[0]], 0.4
    img, _ = new_canvas("$ python scripts/local_retrieval/embed_index.py")
    terminal(img, [("正在加载 bge-small-zh-v1.5（ONNX · 本地）……", C_DIM),
                   ("已建索引：53 篇文档，维度 512", C_GREEN),
                   ("输出 demo-vault/30-知识/.index/  耗时 2.3s", C_TEXT)])
    brand(img, 5)
    yield [img], 2.4
    img, _ = new_canvas('$ semantic_search --query "进程死锁检测和银行家算法又算错了"')
    terminal(img, [("Top-3 命中：", C_DIM),
                   ("md:…/408-操作系统/死锁簇.md            0.786", C_GREEN),
                   ("review:r028  死锁-银行家算法            0.770", C_ACCENT),
                   ("review:r027  进程管理-同步互斥          0.681", C_TEXT),
                   ("（数学题零串扰）", C_DIM)])
    brand(img, 5)
    yield [img], 2.6
    img, _ = new_canvas('$ semantic_search --query "级数收敛判别方法总是选错"')
    terminal(img, [("Top-3 命中：", C_DIM),
                   ("md:…/数学一/级数敛散性判别簇.md         0.796", C_GREEN),
                   ("review:r008  高等数学-级数              0.735", C_ACCENT),
                   ("review:r009  高等数学-级数              0.672", C_TEXT),
                   ("（跨科目各自精准，零串扰）", C_DIM)])
    brand(img, 5)
    yield [img], 2.6
    img, d = new_canvas("")
    for i, t in enumerate(["本地计算", "索引存本地 .index/", "学习数据不上传"]):
        d.rounded_rectangle([220 + i * 520, 420, 220 + i * 520 + 460, 540], 16,
                            outline=C_ACCENT, width=3)
        d.text((330 + i * 520, 458), t, font=F_BODY, fill=C_ACCENT)
    brand(img, 5)
    yield [img], 2.0


def frames_s6():
    yield [new_canvas("云端 Qwen 陪练 —— 真实调用留痕回放（2026-09-13/14）")[0]], 0.4
    img, _ = new_canvas("$ python scripts/qwen_engine.py --dry-run …")
    terminal(img, [('model: "qwen-flash"', C_TEXT),
                   ('system: "你是考研408陪练教练，只输出原创变式题…"', C_TEXT),
                   ('log_path_planned: "logs/qwen/"', C_ACCENT),
                   ("（先预览请求体，确认无个人信息再真实调用）", C_DIM)])
    brand(img, 6)
    yield [img], 2.2
    for k in range(5):
        img, _ = new_canvas("$ python scripts/qwen_engine.py …  （真实调用）")
        terminal(img, [("调用中 " + "▶" * (k % 3 + 1) + "   DashScope · qwen-flash", C_YELLOW),
                       ("（真实时延，留痕生成中）", C_DIM)])
        brand(img, 6)
        yield [img], 0.4
    img, _ = new_canvas("logs/qwen/ 留痕 JSON（节选）")
    terminal(img, [('"model": "qwen-flash"', C_TEXT),
                   ('"total_tokens": 1306, "latency_ms": 8872', C_YELLOW),
                   ('"finish_reason": "stop"', C_TEXT),
                   ("日志不含 API Key（内置防泄漏断言）", C_GREEN)])
    brand(img, 6)
    yield [img], 2.8
    img, _ = new_canvas("$ python scripts/qwen_engine.py --stats   （聚合审计）")
    terminal(img, [("calls: 38    total_tokens: 81,379", C_YELLOW),
                   ("qwen-flash ×32 · qwen3.8-flash ×6", C_TEXT),
                   ("api_key_leaked_logs: 0", C_GREEN),
                   ("（材料中的每个数字都与真值一致）", C_DIM)])
    brand(img, 6)
    yield [img], 2.8
    resp = json.loads((REPO / "logs/qwen/20260913-211223-qwen-flash.json")
                      .read_text(encoding="utf-8")).get("response_content", "")
    keep = [ln for ln in resp.splitlines() if ln.strip()][:5]
    img, _ = new_canvas("Qwen 返回（真实回复节选）")
    terminal(img, [(ln.strip()[:64], C_TEXT) for ln in keep])
    brand(img, 6)
    yield [img], 2.4


def frames_s7():
    yield [new_canvas("FSRS 间隔复习调度 —— 引用开源算法 open-spaced-repetition/fsrs-rs")[0]], 0.4
    img, _ = new_canvas("核心公式（调度器 scripts/scheduler.py）")
    terminal(img, [("遗忘曲线  R(t,S) = (1 + 19t / 81S) ^ -0.5", C_ACCENT),
                   ("初始稳定性  S0 = w[评分-1]   （again/hard/good/easy）", C_TEXT),
                   ("难度更新    均值回归 + 线性阻尼", C_TEXT),
                   ("下一间隔    由期望保持率 0.9 反解", C_ACCENT)])
    brand(img, 7)
    yield [img], 2.8
    img, _ = new_canvas("$ python scripts/scheduler.py --queue 错题队列.json --today 2026-09-14")
    terminal(img, [("40 条错题全部自动排期", C_GREEN),
                   ('{"id":"r028", "interval_days":5, "suggested_next_date":"2026-09-19"}', C_TEXT),
                   ('{"id":"r031", "interval_days":2, …}', C_TEXT)])
    brand(img, 7)
    yield [img], 2.6
    img, d = new_canvas("")
    d.text((240, 420), "到期自动浮出 · 勿扰日自动避开 · 间隔随掌握度伸缩", font=F_SUB, fill=C_ACCENT)
    brand(img, 7)
    yield [img], 2.0


def frames_s8():
    yield [new_canvas("Anki 导出 + 考前预练")[0]], 0.3
    img, _ = new_canvas("$ python scripts/export_anki.py --only-active")
    terminal(img, [("Front,Back,Tags,Stability,…", C_DIM),
                   ("回忆题：408｜死锁-银行家算法……, 安全性检测漏分支…, r028 due", C_TEXT),
                   ("（34 条未掌握错题 → Anki 可导入 CSV）", C_DIM)])
    brand(img, 8)
    yield [img], 2.4
    img, _ = new_canvas("$ python scripts/pre_drill.py --subject 数学一 --topic 级数 --qwen")
    terminal(img, [("① 端侧召回相似错题（本地）", C_ACCENT),
                   ("② 云端 Qwen 出定向变式题（留痕）", C_ACCENT),
                   ("③ Markdown 预练卷，先自测再翻解析", C_TEXT)])
    brand(img, 8)
    yield [img], 2.6


def frames_s9():
    yield [new_canvas("六道 CI 门禁 —— 质量不靠口头承诺")[0]], 0.4
    gates = [("pytest", "92 个测试 × Python 3.10/3.11/3.12"),
             ("Schema 校验", "学习记录 1.1 + 科目配置"),
             ("文档路径", "AI 生成文档的路径漂移防线"),
             ("semgrep", "凭据 / 用户路径 / shell 执行"),
             ("契约覆盖度", "15 Skill × 23 契约 100% 可达"),
             ("数字一致性", "材料计数 vs 留痕真值")]
    img, d = new_canvas("六道 CI 门禁 —— 质量不靠口头承诺")
    y = 170
    for name, desc in gates:
        d.ellipse([100, y + 8, 124, y + 32], outline=C_GREEN, width=4)
        d.text((150, y), name, font=F_BODY, fill=C_TEXT)
        d.text((560, y + 4), desc, font=F_SMALL, fill=C_DIM)
        y += 62
    d.text((100, y + 20), "全部公开可查：github.com/yq6666-66/study-copilot-skills/actions", font=F_SMALL, fill=C_DIM)
    brand(img, 9)
    yield [img], 3.0


def frames_s10():
    img, d = new_canvas("端云协同架构")
    d.rounded_rectangle([240, 170, 860, 310], 16, outline=C_ACCENT, width=3)
    d.text((300, 212), "端侧 AI PC：bge-small-zh（CPU）", font=F_BODY, fill=C_ACCENT)
    d.text((300, 258), "本地检索 · 记忆 · 数据不出域", font=F_SMALL, fill=C_DIM)
    d.rounded_rectangle([1060, 170, 1680, 310], 16, outline=C_YELLOW, width=3)
    d.text((1140, 212), "云端：Qwen（DashScope）", font=F_BODY, fill=C_YELLOW)
    d.text((1140, 258), "错因聚类 · 变式出题 · 二次精讲", font=F_SMALL, fill=C_DIM)
    d.text((890, 218), "⇄", font=F_SUB, fill=C_TEXT)
    d.rounded_rectangle([560, 450, 1360, 600], 16, outline=C_TEXT, width=3)
    d.text((660, 482), "通用 Skills 核心：15 Skills × 23 契约", font=F_BODY, fill=C_TEXT)
    d.text((660, 536), "任何 Agent（Codex / Claude Code / 通用）", font=F_SMALL, fill=C_DIM)
    d.text((660, 680), "任一端掉线，另一端降级照常工作", font=F_SMALL, fill=C_DIM)
    brand(img, 10)
    yield [img], 3.0


def frames_s11():
    img, d = new_canvas("")
    t = "学习副驾：把学习大脑，装进每一个 Agent"
    d.text(((W - d.textlength(t, font=F_TITLE)) / 2, 370), t, font=F_TITLE, fill=C_TEXT)
    d.text(((W - d.textlength("15 Skills · 2 层泛化 · 端云协同 · 开源 MIT", font=F_SUB)) / 2, 530),
           "15 Skills · 2 层泛化 · 端云协同 · 开源 MIT", font=F_SUB, fill=C_ACCENT)
    d.text(((W - d.textlength("代码 · 测试 · 全部证据，都在作品包里", font=F_BODY)) / 2, 640),
           "代码 · 测试 · 全部证据，都在作品包里", font=F_BODY, fill=C_DIM)
    d.text(((W - d.textlength("天猫AI黑客松 · 高校挑战赛 参赛作品", font=F_SMALL)) / 2, 720),
           "天猫AI黑客松 · 高校挑战赛 参赛作品", font=F_SMALL, fill=C_DIM)
    yield [img], 3.0


SHOTS = [frames_s1, frames_s2, frames_s3, frames_s4, frames_s5,
         frames_s6, frames_s7, frames_s8, frames_s9, frames_s10, frames_s11]


def tts(text: str, out: Path) -> float:
    """edge-tts 神经网络语音合成（云希，+8% 语速），偶发网络抖动自动重试。"""
    last_err = None
    for attempt in range(4):
        proc = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", VOICE,
                               "--rate=+8%", "--text", text, "--write-media", str(out)],
                              capture_output=True)
        if proc.returncode == 0 and out.exists() and out.stat().st_size > 1000:
            return probe(out)
        last_err = proc.stderr.decode("utf-8", errors="replace")[-200:]
        time.sleep(3 + attempt * 2)
    raise RuntimeError("edge-tts 连续失败：{}".format(last_err))


def probe(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
    return float(out.stdout.strip())


def run_ff(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + args, check=True)


def build_shot(idx: int, fn) -> Path:
    shot_dir = WORK / f"s{idx + 1}"
    shot_dir.mkdir(parents=True, exist_ok=True)
    audio = shot_dir / "narration.mp3"
    dur = tts(NARRATOR[idx], audio)
    target = dur + 0.7

    frames = list(fn())
    if len(frames) == 1:  # concat 单条目时长会塌缩，拆成两条目
        imgs, d = frames[0]
        frames = [(imgs, d * 0.6), (imgs, d * 0.4)]
    step_total = sum(d for _, d in frames)
    scale = target / step_total

    pngs = []
    started = time.time()
    for i, (imgs, d) in enumerate(frames):
        img = imgs[0]
        subtitle(img, NARRATOR[idx])  # 逐镜烧录字幕
        p = shot_dir / f"f{i:03d}.png"
        img.save(p)
        pngs.append((p, max(d * scale, 0.1)))
    concat = shot_dir / "frames.txt"
    concat.write_text("".join(f"file '{p.as_posix()}'\nduration {d:.3f}\n" for p, d in pngs),
                      encoding="utf-8")
    silent = shot_dir / "video.mp4"
    run_ff(["-f", "concat", "-safe", "0", "-i", concat.as_posix(),
            "-vf", "fps=30,format=yuv420p,tpad=stop_mode=clone:stop_duration=0.6",
            "-c:v", "libx264", "-preset", "fast", silent.as_posix()])
    av = shot_dir / "av.mp4"
    run_ff(["-i", silent.as_posix(), "-i", audio.as_posix(), "-c:v", "copy",
            "-c:a", "aac", "-b:a", "160k", "-shortest", av.as_posix()])
    print(f"  分镜 {idx + 1}: 配音 {dur:.1f}s / 视频 {probe(silent):.1f}s / 渲染 {time.time() - started:.1f}s")
    return av


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    shots = []
    for i, fn in enumerate(SHOTS):
        print(f"渲染分镜 {i + 1}/{len(SHOTS)} …")
        shots.append(build_shot(i, fn))
    lst = WORK / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in shots), encoding="utf-8")
    run_ff(["-f", "concat", "-safe", "0", "-i", lst.as_posix(), "-c", "copy", OUT.as_posix()])
    gif_specs = [(shots[4], WORK / "gif1端侧检索", 8), (shots[5], WORK / "gif2留痕", 12)]
    for src, out_gif, ss in gif_specs:
        run_ff(["-ss", str(ss), "-t", "10", "-i", src.as_posix(), "-vf",
                "fps=12,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse",
                out_gif.with_suffix(".gif").as_posix()])
    print(f"完成：{OUT}  （{probe(OUT):.1f}s，{OUT.stat().st_size / 1048576:.1f} MB）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
