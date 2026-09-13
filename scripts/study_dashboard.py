# -*- coding: utf-8 -*-
"""静态 HTML 学习仪表盘：单文件、零 JS、全内联 CSS/SVG。

渲染内容：
- 科目掌握度色块卡（mastered/due/retesting/pending 四色块 + 平均稳定性 + 7 日待复测）
- 未来 7 天 FSRS 复习负载条（纯 CSS 宽度条）
- FSRS 遗忘曲线 SVG（S=2/7/21 三条曲线，公式来自 scripts/scheduler）
- 执行摘要段：--qwen-summary 时由云端 Qwen 生成（真实留痕），否则占位

安全：所有队列文本经 html.escape 注入；文件 I/O 仅 main() 内联守卫（禁 '..' + 限仓库目录）；
核心 render_html(stats, summary) 只收数据不碰路径。

CLI：
    python scripts/study_dashboard.py --queue demo-vault/30-知识/错题队列.json --out dist/dashboard.html
    python scripts/study_dashboard.py --queue ... --qwen-summary --out docs/competition/学习仪表盘示例.html
"""
from __future__ import annotations

import argparse
import html
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import scheduler as sc  # noqa: E402
import study_report as sr  # noqa: E402

STATUS_COLORS = {"mastered": "#22c55e", "due": "#f59e0b",
                 "retesting": "#ef4444", "pending": "#64748b"}
_CSS = """
body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:2rem}
h1{font-size:1.4rem} h2{font-size:1.05rem;color:#5eead4;margin-top:2rem}
.cards{display:flex;flex-wrap:wrap;gap:1rem}
.card{background:#1e293b;border-radius:12px;padding:1rem 1.2rem;min-width:220px}
.card h3{margin:0 0 .6rem;font-size:1rem}
.blocks{display:flex;gap:4px;margin:.4rem 0}
.blk{height:14px;border-radius:3px}
.meta{font-size:.8rem;color:#94a3b8}
.bar-row{display:flex;align-items:center;gap:.6rem;margin:.35rem 0;font-size:.85rem}
.bar-row .day{width:6.5rem;color:#94a3b8}
.bar{height:16px;background:#0ea5e9;border-radius:4px;min-width:2px}
.bar-row .n{color:#94a3b8}
.summary{background:#1e293b;border-left:4px solid #5eead4;padding:.8rem 1rem;border-radius:0 8px 8px 0;white-space:pre-wrap}
svg{background:#1e293b;border-radius:12px}
"""


def _forget_svg() -> str:
    """三条遗忘曲线 R(t)（S=2/7/21），t∈[0,30]，纯 SVG polyline。"""
    paths = []
    for s_val, color in ((2, "#ef4444"), (7, "#f59e0b"), (21, "#22c55e")):
        pts = []
        for t in range(0, 31):
            r = sc.retrievability(float(t), float(s_val))
            x = 60 + t * 18
            y = 200 - r * 160
            pts.append("{},{}".format(x, round(y, 1)))
        paths.append('<polyline fill="none" stroke="{}" stroke-width="2.5" points="{}"/>'.format(
            color, " ".join(pts)))
        paths.append('<text x="{}" y="{}" fill="{}" font-size="12">S={}</text>'.format(
            60 + 30 * 18 + 8, round(200 - sc.retrievability(30.0, float(s_val)) * 160, 1), color, s_val))
    return ('<svg width="660" height="230" viewBox="0 0 660 230" role="img" '
            'aria-label="FSRS 遗忘曲线">' + "".join(paths) +
            '<text x="60" y="222" fill="#94a3b8" font-size="11">t（天） 0 → 30；纵轴 可提取概率 R</text></svg>')


def render_html(stats: dict, summary: str | None = None) -> str:
    esc = html.escape
    today = stats["today"]
    out = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1">',
           '<title>学习仪表盘 · {}</title><style>{}</style></head><body>'.format(
               esc(today.isoformat()), _CSS)]
    out.append("<h1>学习仪表盘 <span class='meta'>基准日 {} · 由 scripts/study_dashboard.py 生成</span></h1>".format(
        esc(today.isoformat())))

    out.append("<h2>科目掌握度</h2><div class='cards'>")
    for sub, s in sorted(stats["by_subject"].items()):
        blocks = []
        for st_name in ("mastered", "due", "retesting", "pending"):
            n = s["st"].get(st_name, 0)
            if n:
                blocks.append("<div class='blk' title='{}: {}' style='background:{};width:{}px'></div>".format(
                    esc(st_name), n, STATUS_COLORS[st_name], 10 + n * 8))
        out.append("<div class='card'><h3>{}</h3><div class='blocks'>{}</div>"
                   "<div class='meta'>条目 {} · 平均稳定性 {:.1f} · 7日待复测 {}</div></div>".format(
                       esc(sub), "".join(blocks), s["n"], s["sum_s"] / max(s["n"], 1), s["due7"]))
    out.append("</div>")

    out.append("<h2>未来 7 天复习负载（FSRS 建议日）</h2>")
    bucket = stats["bucket"]
    max_n = max(bucket.values()) if bucket else 1
    for i in range(7):
        day = (today + timedelta(days=i)).isoformat()
        n = bucket.get(day, 0)
        width = round(n / max_n * 320) if max_n else 0
        out.append("<div class='bar-row'><span class='day'>{}</span>"
                   "<div class='bar' style='width:{}px'></div><span class='n'>{}</span></div>".format(
                       esc(day), width, n))

    out.append("<h2>错题热点（未掌握）</h2><ul>")
    for topic, n in stats["hot"].most_common(8):
        out.append("<li>{}（{} 条）</li>".format(esc(topic), n))
    out.append("</ul>")

    out.append("<h2>FSRS 遗忘曲线（S=2/7/21）</h2>" + _forget_svg())

    out.append("<h2>执行摘要</h2>")
    out.append("<div class='summary'>{}</div>".format(
        esc(summary) if summary else "（未启用 --qwen-summary：运行带该参数生成云端执行摘要并留痕）"))
    out.append("</body></html>")
    return "\n".join(out)


def qwen_summary(stats: dict, model: str = "qwen-flash") -> str:
    """云端 Qwen 基于真实统计写一段执行摘要（真实调用留痕）。"""
    from qwen_engine import call_qwen
    lines = ["科目概览："]
    for sub, s in sorted(stats["by_subject"].items()):
        lines.append("- {}：{} 条（mastered {}、due {}、retesting {}、pending {}），7日待复测 {}".format(
            sub, s["n"], s["st"].get("mastered", 0), s["st"].get("due", 0),
            s["st"].get("retesting", 0), s["st"].get("pending", 0), s["due7"]))
    lines.append("7 天负载：{}".format(
        "；".join("{}:{}条".format(d, n) for d, n in sorted(stats["bucket"].items())) or "无"))
    result = call_qwen([
        {"role": "system", "content": "你是学习教练。基于给定统计写一段 120 字内执行摘要，中文，只引用给定数字，不虚构。"},
        {"role": "user", "content": "\n".join(lines)},
    ], model=model)
    return result["content"].strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="静态 HTML 学习仪表盘")
    parser.add_argument("--queue", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--today", default=None)
    parser.add_argument("--qwen-summary", action="store_true",
                        help="执行摘要由云端 Qwen 生成（真实留痕）")
    args = parser.parse_args()

    # 内联路径守卫（本模块唯一接触文件处）：禁 '..' 段 + 限仓库目录内
    for raw in (args.queue, args.out):
        if ".." in Path(raw).parts:
            print("路径不允许包含 '..' 段：{}".format(raw))
            return 2
    queue_path = Path(args.queue).resolve()
    out_path = Path(args.out).resolve()
    for p in (queue_path, out_path):
        if p != REPO and REPO not in p.parents:
            print("路径必须位于仓库目录内：{}".format(p))
            return 2

    today = date.fromisoformat(args.today) if args.today else date.today()
    stats = sr.compute_stats(queue_path, today)
    summary = qwen_summary(stats) if args.qwen_summary else None
    doc = render_html(stats, summary)
    parent = out_path.parent
    if not parent.is_dir():
        parent.mkdir(exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    print("仪表盘已生成 → {}".format(out_path))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
