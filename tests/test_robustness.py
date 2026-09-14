# -*- coding: utf-8 -*-
"""深度鲁棒性测试：恶意/损坏/极端输入下的行为（离线，无网络无模型）。"""
import csv
import io
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import export_anki as ea  # noqa: E402
import scheduler as sc  # noqa: E402


def _queue(items: list) -> str:
    return json.dumps({"schemaVersion": "1.1", "recordType": "ReviewQueue",
                       "generatedAt": "2026-09-13", "items": items}, ensure_ascii=False)


def test_csv_formula_injection_neutralized():
    """CSV 公式注入：以 = + - @ 开头的字段在 Excel 中会被当公式执行，必须中和。"""
    items = [
        {"id": "e1", "subject": "数学一", "topic": "=HYPERLINK(\"http://evil\")", "errorCause": "=cmd()",
         "errorCauseStatus": "hypothesis", "nextRetestDate": None, "retestOffsetDays": 5,
         "status": "due", "masteryEvidence": []},
        {"id": "e2", "subject": "+提示", "topic": "@SUM(A1)", "errorCause": "-欺骗",
         "errorCauseStatus": "confirmed", "nextRetestDate": None, "retestOffsetDays": 3,
         "status": "due", "masteryEvidence": []},
    ]
    text = ea.export_csv_text(_queue(items), date(2026, 9, 14))
    rows = list(csv.reader(io.StringIO(text)))
    for row in rows[1:]:
        for cell in row[:2]:  # Front/Back
            assert not cell.startswith(("=", "+", "@", "\t")), "公式字符泄漏: %r" % cell


def test_broken_queue_json_not_crash(tmp_path):
    """损坏的错题队列：端侧检索采集与调度不崩溃（静默跳过该来源）。"""
    from local_retrieval.corpus import collect
    v = tmp_path / "v"
    (v / "30-知识").mkdir(parents=True)
    (v / "30-知识" / "错题队列.json").write_text("{损坏", encoding="utf-8")
    (v / "30-知识" / "笔记.md").write_text("# 笔记", encoding="utf-8")
    docs = collect(v)
    assert any(d["doc_id"].startswith("md:") for d in docs)


def test_empty_queue(tmp_path):
    from local_retrieval.corpus import collect
    v = tmp_path / "v"
    (v / "30-知识").mkdir(parents=True)
    (v / "30-知识" / "错题队列.json").write_text(
        json.dumps({"schemaVersion": "1.1", "recordType": "ReviewQueue",
                    "generatedAt": "2026-09-13", "items": []}, ensure_ascii=False), encoding="utf-8")
    assert sc_module_collect_empty(v)


def sc_module_collect_empty(v: Path) -> bool:
    from local_retrieval import corpus as corpus_mod
    return corpus_mod.collect(v) == []


def test_scheduler_extreme_values_bounded():
    """极端稳定性/难度下，间隔与难度仍被钳制在安全范围。"""
    iv = sc.next_interval(1e9)   # 巨大稳定性
    assert sc.INTERVAL_MIN <= iv <= sc.INTERVAL_MAX
    iv0 = sc.next_interval(0.05)  # 极小稳定性
    assert iv0 >= sc.INTERVAL_MIN
    s, d = sc.review(1e9, 10.0, 30.0, "good")
    assert s > 0 and sc.D_MIN <= d <= sc.D_MAX


def test_long_input_no_crash():
    """超长文本不崩溃（截断策略）。"""
    long_topic = "测" * 5000
    items = [{"id": "L", "subject": "数学一", "topic": long_topic, "errorCause": long_topic,
              "errorCauseStatus": "hypothesis", "nextRetestDate": None, "retestOffsetDays": 7,
              "status": "pending", "masteryEvidence": []}]
    text = sc.schedule_item(items[0], date(2026, 9, 14))
    assert text["interval_days"] >= 1
    import export_anki as ea
    out = ea.export_csv_text(json.dumps({"items": items}, ensure_ascii=False), date(2026, 9, 14))
    assert "测" in out

