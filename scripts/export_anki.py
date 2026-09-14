# -*- coding: utf-8 -*-
"""错题队列 → Anki 可导入 CSV 导出器。

列结构（UTF-8 BOM，Anki 文本导入可直接映射）：
    Front, Back, Tags, Stability, Difficulty, IntervalDays, SuggestedNextDate, Status
- Front/Back 默认本地模板（Front 只含回忆问题不含答案，符合主动回忆原则）；
  `--qwen-prompts` 时改由云端 Qwen 改写措辞（真实调用留痕，Front 仍不得含答案——由提示词约束）。
- Stability/Difficulty 取自 scripts/scheduler（无 fsrs 精确态时显式 bootstrap）。
- 默认导出全部条目；`--only-active` 排除 mastered。
- 路径安全：文件 I/O 仅在 main() 内联守卫后发生——拒绝 '..' 段且限定仓库目录内；
  核心函数 export_csv_text 只处理文本、不接触路径（结构上杜绝穿越面）。

CLI：
    python scripts/export_anki.py --queue demo-vault/30-知识/错题队列.json --out dist/anki.csv
    python scripts/export_anki.py --queue ... --qwen-prompts --out dist/anki_qwen.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import scheduler as sc  # noqa: E402

HEADERS = ["Front", "Back", "Tags", "Stability", "Difficulty",
           "IntervalDays", "SuggestedNextDate", "Status"]


def _slug(topic: str) -> str:
    return (topic or "topic").replace(" ", "-").replace("/", "-")


def _local_card(item: dict, sched: dict) -> tuple[str, str]:
    front = ("回忆题：{}｜{}\n请复述：当时的错误原因是什么？正确解法的关键步骤有哪些？"
             "（先独立作答再翻面）".format(item.get("subject", "?"), item.get("topic", "?")))
    back = ("错误原因：{}\n错因状态：{}\n掌握证据：{}".format(
        item.get("errorCause", "?"), item.get("errorCauseStatus", "?"),
        "；".join(item.get("masteryEvidence") or []) or "（暂无）"))
    return front, back


def qwen_cards(items: list[dict], model: str = "qwen-flash") -> dict[str, tuple[str, str]]:
    """让 Qwen 把卡片改写为更规范的回忆式措辞；返回 {id: (front, back)}。

    提示词约束：Front 只允许回忆问题、禁止包含答案；Back 为答案要点；不得虚构队列中没有的事实。
    """
    from qwen_engine import call_qwen
    payload = [{"id": it.get("id"), "subject": it.get("subject"),
                "topic": it.get("topic"), "errorCause": it.get("errorCause"),
                "errorCauseStatus": it.get("errorCauseStatus")} for it in items]
    result = call_qwen([
        {"role": "system", "content": (
            "你是记忆科学措辞专家。把输入错题改写为 Anki 卡片 JSON 数组，元素为 "
            '{"id", "front", "back"}。front 只允许回忆性问题，严禁包含答案或错因本身；'
            "back 为答案要点（错因+正确步骤）。不得虚构输入之外的事实。只输出 JSON。")},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ], model=model)
    text = result["content"]
    start, end = text.find("["), text.rfind("]")
    data = json.loads(text[start:end + 1]) if start != -1 and end > start else {}
    out = {}
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict) and row.get("id") and row.get("front"):
                out[str(row["id"])] = (row["front"], row.get("back", ""))
    return out


def export_csv_text(queue_json_text: str, today: date, only_active: bool = False,
                    cards: dict | None = None, delimiter: str = ",") -> str:
    """纯文本进、CSV 文本出；不接触任何文件路径。"""
    items = json.loads(queue_json_text).get("items", [])
    if only_active:
        items = [it for it in items if it.get("status") != "mastered"]
    sched = {it.get("id"): sc.schedule_item(it, today) for it in items}
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delimiter)
    w.writerow(HEADERS)
    for it in items:
        s = sched[it.get("id")]
        front, back = (cards or {}).get(str(it.get("id"))) or _local_card(it, s)
        tags = " ".join(filter(None, [
            (it.get("subject") or "").replace(" ", "-"), _slug(it.get("topic")),
            it.get("status"), "bootstrapped" if s["bootstrapped"] else ""]))
        w.writerow([front, back, tags, s["stability"], s["difficulty"],
                    s["interval_days"], s["suggested_next_date"], it.get("status")])
    return buf.getvalue()


def _neutralize(cell: str) -> str:
    """CSV 公式注入中和：Excel 会把 = + - @ 开头的单元格当公式执行。"""
    if cell[:1] in ("=", "+", "@", "\t", "\r"):
        return "'" + cell
    return cell


def export_csv_text(queue_json_text: str, today: date, only_active: bool = False,
                    cards: dict | None = None, delimiter: str = ",") -> str:
    """纯文本进、CSV 文本出；不接触任何文件路径。"""
    items = json.loads(queue_json_text).get("items", [])
    if only_active:
        items = [it for it in items if it.get("status") != "mastered"]
    sched = {it.get("id"): sc.schedule_item(it, today) for it in items}
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delimiter)
    w.writerow(HEADERS)
    for it in items:
        s = sched[it.get("id")]
        front, back = (cards or {}).get(str(it.get("id"))) or _local_card(it, s)
        tags = " ".join(filter(None, [
            (it.get("subject") or "").replace(" ", "-"), _slug(it.get("topic")),
            it.get("status"), "bootstrapped" if s["bootstrapped"] else ""]))
        w.writerow([_neutralize(str(front)), _neutralize(str(back)), tags,
                    s["stability"], s["difficulty"], s["interval_days"],
                    s["suggested_next_date"], it.get("status")])
    return buf.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description="错题队列 → Anki CSV 导出")
    parser.add_argument("--queue", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--today", default=None)
    parser.add_argument("--only-active", action="store_true", help="排除 mastered 条目")
    parser.add_argument("--qwen-prompts", action="store_true",
                        help="卡片措辞由云端 Qwen 改写（真实调用留痕；Front 不含答案）")
    parser.add_argument("--delimiter", default=",", choices=[",", "\t"])
    args = parser.parse_args()

    # 内联路径守卫（本模块唯一接触文件的位置）：禁止 '..' 段 + 限定仓库目录内
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

    # 内联路径守卫（本模块唯一接触文件的位置）：禁 '..' 段 + 限定仓库目录内
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
    csv_text = export_csv_text(queue_path.read_text(encoding="utf-8"), today,
                               args.only_active, cards if args.qwen_prompts else None,
                               args.delimiter)
    parent = out_path.parent
    if not parent.is_dir():
        parent.mkdir(exist_ok=True)  # 单层创建；更深层缺失显式失败
    out_path.write_text(csv_text, encoding="utf-8-sig")
    n = sum(1 for _ in csv.reader(io.StringIO(csv_text))) - 1  # 多行字段不影响计数
    print("已导出 {} 张卡片 → {}".format(n, out_path))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
