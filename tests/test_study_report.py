# -*- coding: utf-8 -*-
"""学习周报生成器回归测试（离线，不调 Qwen）。"""
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import study_report as sr  # noqa: E402

QUEUE = {
    "schemaVersion": "1.1", "recordType": "ReviewQueue", "generatedAt": "2026-09-13",
    "items": [
        {"id": "a", "subject": "数学一", "topic": "级数", "errorCause": "判别法混用",
         "errorCauseStatus": "hypothesis", "nextRetestDate": None, "retestOffsetDays": 7,
         "status": "due", "masteryEvidence": []},
        {"id": "b", "subject": "数学一", "topic": "级数", "errorCause": "漏单调性",
         "errorCauseStatus": "confirmed", "nextRetestDate": None, "retestOffsetDays": None,
         "status": "mastered", "masteryEvidence": ["x"]},
        {"id": "c", "subject": "408-操作系统", "topic": "死锁", "errorCause": "漏分支",
         "errorCauseStatus": "confirmed", "nextRetestDate": "2026-09-14", "retestOffsetDays": None,
         "status": "retesting", "masteryEvidence": []},
    ],
}


def _queue_file(tmp_path: Path) -> Path:
    q = tmp_path / "q.json"
    import json
    q.write_text(json.dumps(QUEUE, ensure_ascii=False), encoding="utf-8")
    return q


def test_report_sections_present(tmp_path):
    report, sched = sr.build_report(_queue_file(tmp_path), date(2026, 9, 14))
    for sec in ("科目掌握概览", "错题热点", "未来 7 天复习负载", "洞察与建议"):
        assert sec in report
    assert len(sched) == 3
    assert "<!--INSIGHTS-->" in report  # 占位待填


def test_subject_rows_and_hotspots(tmp_path):
    report, _ = sr.build_report(_queue_file(tmp_path), date(2026, 9, 14))
    assert "| 数学一 | 2 |" in report
    assert "| 408-操作系统 | 1 |" in report
    assert "级数（1 条）" in report  # mastered 不计入热点


def test_seven_day_load_uses_fsrs(tmp_path):
    report, sched = sr.build_report(_queue_file(tmp_path), date(2026, 9, 14))
    assert "未来 7 天复习负载" in report
    assert all(s["interval_days"] >= 1 for s in sched)
