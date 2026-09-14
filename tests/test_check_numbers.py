# -*- coding: utf-8 -*-
"""数字一致性门禁回归测试：构造假仓库树验证一致/漂移两类场景。"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import check_numbers as cn  # noqa: E402


def _fake_root(tmp: Path, doc_calls: int = 2, logs_calls: int = 2, readme_extra_ok: bool = True) -> Path:
    logs = tmp / "logs" / "qwen"
    logs.mkdir(parents=True)
    for i in range(logs_calls):
        (logs / "20260913-21{:02d}00-qwen-flash.json".format(i)).write_text(json.dumps({
            "model": "qwen-flash", "usage": {"total_tokens": 100}}), encoding="utf-8")
    docs = tmp / "docs" / "competition"
    docs.mkdir(parents=True)
    detail = "\n".join("| 20260913-21{:02d}00 | qwen-flash | 100 | 50 |".format(i) for i in range(doc_calls))
    (docs / "千问证据总览.md").write_text(
        "真实调用：**{} 次**\n累计 token：**{}**\n".format(doc_calls, doc_calls * 100) + detail, encoding="utf-8")
    (docs / "AI技术实践说明.md").write_text(
        "共 {} 次真实调用全部留痕，累计 {} tokens".format(doc_calls, "{:,}".format(doc_calls * 100)),
        encoding="utf-8")
    return tmp


def test_consistent_tree_passes(tmp_path):
    root = _fake_root(tmp_path)
    assert cn.check(root) == []


def test_drifted_doc_count_detected(tmp_path):
    root = _fake_root(tmp_path, doc_calls=3, logs_calls=2)
    bad = cn.check(root)
    joined = " ".join(bad)
    assert "证据总览" in joined and "实践说明" in joined


def test_wrong_token_sum_detected(tmp_path):
    root = _fake_root(tmp_path)
    ov = root / "docs" / "competition" / "千问证据总览.md"
    ov.write_text(ov.read_text(encoding="utf-8").replace("**200**", "**999**"), encoding="utf-8")
    assert any("token" in b for b in cn.check(root))


def test_missing_practice_sentence_detected(tmp_path):
    root = _fake_root(tmp_path)
    prac = root / "docs" / "competition" / "AI技术实践说明.md"
    prac.write_text(prac.read_text(encoding="utf-8").replace(
        "共 {} 次真实调用全部留痕".format(2), "调用若干次"), encoding="utf-8")
    assert any("实践说明" in b for b in cn.check(root))
