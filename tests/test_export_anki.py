# -*- coding: utf-8 -*-
"""export_anki 回归测试：列结构/过滤/引用转义/FSRS 字段/路径守卫。"""
import csv
import io
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import export_anki as ea  # noqa: E402

QUEUE = {
    "schemaVersion": "1.1", "recordType": "ReviewQueue", "generatedAt": "2026-09-13",
    "items": [
        {"id": "a", "subject": "数学一", "topic": "级数,判敛", "errorCause": "判别法混用",
         "errorCauseStatus": "hypothesis", "nextRetestDate": None, "retestOffsetDays": 7,
         "status": "due", "masteryEvidence": []},
        {"id": "b", "subject": "数学一", "topic": "极限", "errorCause": "洛必达误用",
         "errorCauseStatus": "confirmed", "nextRetestDate": None, "retestOffsetDays": None,
         "status": "mastered", "masteryEvidence": ["x"]},
    ],
}


def _rows(text: str) -> list:
    return list(csv.reader(io.StringIO(text)))


def test_headers_and_row_count():
    out = ea.export_csv_text(json.dumps(QUEUE), date(2026, 9, 14))
    rows = _rows(out)
    assert rows[0] == ea.HEADERS
    assert len(rows) == 3  # header + 2 items


def test_only_active_excludes_mastered():
    out = ea.export_csv_text(json.dumps(QUEUE), date(2026, 9, 14), only_active=True)
    rows = _rows(out)
    assert len(rows) == 2
    assert "mastered" not in out


def test_comma_in_topic_is_quoted():
    out = ea.export_csv_text(json.dumps(QUEUE), date(2026, 9, 14))
    rows = _rows(out)
    assert any("级数,判敛" in cell for cell in rows[1])  # csv 模块正确转义


def test_fsrs_fields_present_and_bootstrapped_tag():
    out = ea.export_csv_text(json.dumps(QUEUE), date(2026, 9, 14))
    rows = _rows(out)
    hdr = rows[0]
    r = rows[1]
    assert float(r[hdr.index("Stability")]) > 0
    assert int(r[hdr.index("IntervalDays")]) >= 1
    assert "bootstrapped" in r[hdr.index("Tags")]


def test_qwen_cards_override_used():
    cards = {"a": ("回忆：级数判敛第一步？", "先判别法选择树")}
    out = ea.export_csv_text(json.dumps(QUEUE), date(2026, 9, 14), cards=cards)
    rows = _rows(out)
    assert rows[1][0] == "回忆：级数判敛第一步？"
    assert rows[2][0] != cards["a"][0]  # 无卡片映射的条目走本地模板


def test_cli_path_guard(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["export_anki.py", "--queue", "../../etc/passwd",
                                      "--out", str(tmp_path / "x.csv")])
    assert ea.main() == 2
    assert ".." in capsys.readouterr().out


def test_cli_outside_repo_guard(tmp_path, monkeypatch, capsys):
    q = tmp_path / "q.json"
    q.write_text(json.dumps(QUEUE), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["export_anki.py", "--queue", str(q),
                                      "--out", str(tmp_path / "x.csv")])
    assert ea.main() == 2
    assert "仓库目录内" in capsys.readouterr().out
