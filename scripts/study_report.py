# -*- coding: utf-8 -*-
"""学习周报生成器：从错题队列 + FSRS 调度生成 Markdown 周报。

结构：科目掌握概览（status 分布/平均稳定性/到期复测数）→ 错题热点（topic 频次 Top）→
未来 7 天复习负载（按 FSRS 建议日分桶）→ 洞察段（--qwen 时由云端 Qwen 生成并留痕，
否则占位提示）。

CLI：
    python scripts/study_report.py --queue demo-vault/30-知识/错题队列.json --out dist/周报.md
    python scripts/study_report.py --queue ... --qwen      # 洞察段走真实 Qwen 调用
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import scheduler as sc  # noqa: E402

PROGRESS_BLOCK = re.compile(r"```json\n(.*?)```", re.S)


def _progress_from_md(md_path: Path) -> dict | None:
    if not md_path.exists():
        return None
    for block in PROGRESS_BLOCK.findall(md_path.read_text(encoding="utf-8")):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if data.get("recordType") == "ProgressSnapshot":
            return data
    return None


def build_report(queue_path: Path, today: date, vault_root: Path | None = None) -> tuple[str, list[dict]]:
    data = json.loads(queue_path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    sched = [sc.schedule_item(it, today) for it in items]

    lines = ["# 学习周报（{} 起）".format(today.isoformat()), ""]
    # 1) 科目掌握概览
    by_subject: dict = {}
    for it, s in zip(items, sched):
        sub = it.get("subject") or "?"
        slot = by_subject.setdefault(sub, {"n": 0, "st": Counter(), "sum_s": 0.0, "due7": 0})
        slot["n"] += 1
        slot["st"][it.get("status")] += 1
        slot["sum_s"] += s["stability"]
        if s["suggested_next_date"] <= (today + timedelta(days=7)).isoformat():
            slot["due7"] += 1
    lines += ["## 科目掌握概览", "", "| 科目 | 条目 | mastered | due | retesting | pending | 平均稳定性 | 7日内待复测 |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for sub, s in sorted(by_subject.items()):
        lines.append("| {} | {} | {} | {} | {} | {} | {:.1f} | {} |".format(
            sub, s["n"], s["st"].get("mastered", 0), s["st"].get("due", 0),
            s["st"].get("retesting", 0), s["st"].get("pending", 0),
            s["sum_s"] / max(s["n"], 1), s["due7"]))
    # 2) 错题热点
    hot = Counter((it.get("topic") or "?") for it in items if it.get("status") != "mastered")
    lines += ["", "## 错题热点（未掌握条目）", ""]
    for topic, n in hot.most_common(6):
        lines.append("- {}（{} 条）".format(topic, n))
    # 3) 7 天负载
    bucket: Counter = Counter()
    for s in sched:
        d = s["suggested_next_date"]
        if d <= (today + timedelta(days=7)).isoformat():
            bucket[d] += 1
    lines += ["", "## 未来 7 天复习负载（FSRS 建议日）", ""]
    for day in sorted(bucket):
        lines.append("- {}：{} 条".format(day, bucket[day]))
    lines += ["", "## 洞察与建议", "", "<!--INSIGHTS-->", ""]
    return "\n".join(lines), sched


def fill_insights(report: str, stats_text: str, model: str = "qwen-flash") -> str:
    from qwen_engine import call_qwen
    result = call_qwen([
        {"role": "system", "content": "你是学习教练，基于给定周报统计输出 3 条可执行建议，中文，每条一行，不虚构数据。"},
        {"role": "user", "content": stats_text},
    ], model=model)
    return report.replace("<!--INSIGHTS-->", result["content"].strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="学习周报生成器")
    parser.add_argument("--queue", required=True)
    parser.add_argument("--today", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--qwen", action="store_true", help="洞察段调用云端 Qwen（真实留痕）")
    args = parser.parse_args()
    today = date.fromisoformat(args.today) if args.today else date.today()
    report, sched = build_report(Path(args.queue), today)
    if args.qwen:
        stats = report.split("## 洞察与建议")[0]
        report = fill_insights(report, stats)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report, encoding="utf-8")
        print("周报已写入", args.out)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
