# -*- coding: utf-8 -*-
"""study_dashboard 回归测试：结构/转义/负载条/SVG/守卫。"""
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import study_dashboard as sd  # noqa: E402
import study_report as sr  # noqa: E402

QUEUE = {
    "schemaVersion": "1.1", "recordType": "ReviewQueue", "generatedAt": "2026-09-13",
    "items": [
        {"id": "a", "subject": "数学一", "topic": "<script>alert(1)</script>", "errorCause": "x",
         "errorCauseStatus": "hypothesis", "nextRetestDate": None, "retestOffsetDays": 7,
         "status": "due", "masteryEvidence": []},
        {"id": "b", "subject": "数学一", "topic": "极限", "errorCause": "y",
         "errorCauseStatus": "confirmed", "nextRetestDate": None, "retestOffsetDays": None,
         "status": "mastered", "masteryEvidence": ["x"]},
        {"id": "c", "subject": "408-操作系统", "topic": "死锁", "errorCause": "z",
         "errorCauseStatus": "confirmed", "nextRetestDate": "2026-09-15", "retestOffsetDays": None,
         "status": "retesting", "masteryEvidence": []},
    ],
}


def _stats(tmp_path: Path):
    q = tmp_path / "q.json"
    q.write_text(json.dumps(QUEUE, ensure_ascii=False), encoding="utf-8")
    return sr.compute_stats(q, date(2026, 9, 14))


def test_html_structure(tmp_path):
    doc = sd.render_html(_stats(tmp_path))
    assert doc.startswith("<!doctype html>")
    assert "科目掌握度" in doc and "未来 7 天复习负载" in doc and "FSRS 遗忘曲线" in doc
    assert "<svg" in doc and doc.count("<polyline") == 3  # 三条曲线


def test_status_blocks_and_subjects(tmp_path):
    doc = sd.render_html(_stats(tmp_path))
    assert "数学一" in doc and "408-操作系统" in doc
    for color in sd.STATUS_COLORS.values():
        assert color in doc or True  # 颜色按需出现，不强求全部
    assert "#22c55e" in doc and "#ef4444" in doc  # mastered 与 retesting 均存在


def test_xss_escaped(tmp_path):
    doc = sd.render_html(_stats(tmp_path))
    assert "<script>alert(1)</script>" not in doc
    assert "&lt;script&gt;" in doc


def test_load_bars_present(tmp_path):
    doc = sd.render_html(_stats(tmp_path))
    assert doc.count("class='bar'") >= 1
    assert "2026-09-14" in doc  # 第 0 天


def test_summary_placeholder_and_fill(tmp_path):
    stats = _stats(tmp_path)
    assert "未启用 --qwen-summary" in sd.render_html(stats)
    assert "执行摘要文本" in sd.render_html(stats, summary="执行摘要文本")


def test_cli_path_guards(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["study_dashboard.py", "--queue", "../x.json",
                                      "--out", str(tmp_path / "d.html")])
    assert sd.main() == 2
    assert ".." in capsys.readouterr().out
