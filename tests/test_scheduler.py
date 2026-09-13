# -*- coding: utf-8 -*-
"""FSRS 调度器回归测试：公式性质 + 队列集成。"""
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import scheduler as sc  # noqa: E402


def test_forgetting_curve_monotone_and_bounded():
    r0 = sc.retrievability(0, 10)
    r7 = sc.retrievability(7, 10)
    r30 = sc.retrievability(30, 10)
    assert 0.999 < r0 <= 1.0
    assert r0 > r7 > r30 > 0


def test_higher_stability_slower_forgetting():
    assert sc.retrievability(7, 21) > sc.retrievability(7, 4)


def test_next_interval_monotone_in_stability():
    iv = [sc.next_interval(s) for s in (1, 4, 10, 30, 100)]
    assert iv == sorted(iv)
    assert iv[0] >= 1 and iv[-1] <= 365


def test_next_interval_matches_desired_retention():
    s = 10.0
    iv = sc.next_interval(s, 0.9)
    r_at_iv = sc.retrievability(iv, s)
    assert 0.88 <= r_at_iv <= 0.92  # 反解精度


def test_review_again_never_increases_stability():
    s, d = sc.init_state("good")
    ns, nd = sc.review(s, d, 3.0, "again")
    assert ns <= s
    assert sc.D_MIN <= nd <= sc.D_MAX


def test_review_success_increases_stability():
    s, d = sc.init_state("good")
    ns, _ = sc.review(s, d, sc.next_interval(s), "good")
    assert ns > s


def test_schedule_item_bootstrap_vs_exact():
    today = date(2026, 9, 14)
    b = sc.schedule_item({"id": "x", "status": "due"}, today)
    assert b["bootstrapped"] is True and b["stability"] == 7.0
    e = sc.schedule_item({"id": "y", "status": "due", "fsrs": {"s": 30.0, "d": 4.0}}, today)
    assert e["bootstrapped"] is False and e["interval_days"] > b["interval_days"]


def test_queue_cli_payload_shape(tmp_path):
    q = tmp_path / "q.json"
    q.write_text('{"items":[{"id":"a1","subject":"数学一","topic":"级数","status":"due"}]}',
                 encoding="utf-8")
    out = sc.schedule_queue(q, date(2026, 9, 14))
    assert len(out) == 1
    assert set(out[0]) >= {"id", "interval_days", "suggested_next_date", "retrievability_today"}
