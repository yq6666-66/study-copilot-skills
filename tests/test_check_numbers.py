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
    table = "\n".join("| {} | x | y | `20260913-21{:02d}00` |".format(i + 1, i) for i in range(doc_calls))
    detail = "\n".join("| 20260913-21{:02d}00 | qwen-flash | 100 | 50 |".format(i) for i in range(doc_calls))
    (tmp / "README.md").write_text(
        "以下 **{} 次调用**均为\n模型：`qwen-flash` ×{}、`qwen3.8-flash` ×0\n".format(
            doc_calls, doc_calls) + table, encoding="utf-8")
    (tmp / "docs" / "README.en.md").write_text(
        "**{} real calls**, every one trace-logged".format(doc_calls), encoding="utf-8")
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
    assert "README.md" in joined and "证据总览" in joined


def test_wrong_token_sum_detected(tmp_path):
    root = _fake_root(tmp_path)
    ov = root / "docs" / "competition" / "千问证据总览.md"
    ov.write_text(ov.read_text(encoding="utf-8").replace("**200**", "**999**"), encoding="utf-8")
    assert any("token" in b for b in cn.check(root))


def test_missing_model_distribution_detected(tmp_path):
    root = _fake_root(tmp_path)
    r = root / "README.md"
    r.write_text(r.read_text(encoding="utf-8").replace("×2", "×1"), encoding="utf-8")
    assert any("模型分布" in b for b in cn.check(root))
