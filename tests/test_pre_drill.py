# -*- coding: utf-8 -*-
"""pre_drill 回归测试：召回过滤/预练卷结构/Qwen 注入/守卫/缺索引。"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import pre_drill as pd_  # noqa: E402
from local_retrieval.embedder import FakeEmbedder  # noqa: E402
from local_retrieval.index_store import build_index  # noqa: E402

DOCS = [
    {"doc_id": "review:a", "text": "科目：408-操作系统\n知识点：死锁-银行家算法\n错因：安全性检测漏分支",
     "metadata": {"kind": "review", "subject": "408-操作系统", "topic": "死锁-银行家算法"}},
    {"doc_id": "review:b", "text": "科目：数学一\n知识点：级数\n错因：判别法混用",
     "metadata": {"kind": "review", "subject": "数学一", "topic": "级数"}},
]


@pytest.fixture()
def index_dir(tmp_path):
    emb = FakeEmbedder()
    vecs = emb.embed([d["text"] for d in DOCS])
    d = tmp_path / ".index"
    build_index(d, DOCS, vecs, "fake")
    return d


def test_recall_subject_filter(index_dir):
    emb = FakeEmbedder()
    got = pd_.recall(index_dir, emb, "死锁", top_k=5, subject="408-操作系统")
    assert got and all(r["metadata"]["subject"] == "408-操作系统" for r in got)


def test_drill_sheet_lists_recall(index_dir):
    emb = FakeEmbedder()
    rec = pd_.recall(index_dir, emb, "死锁", top_k=2)
    sheet = pd_.build_drill_sheet("408-操作系统 死锁", rec, None)
    assert "考前预练卷" in sheet and "review:a" in sheet
    assert "--no-qwen 模式" in sheet  # 无 Qwen 段占位


def test_drill_sheet_with_qwen_section(index_dir):
    emb = FakeEmbedder()
    rec = pd_.recall(index_dir, emb, "死锁", top_k=2)
    sheet = pd_.build_drill_sheet("q", rec, "### 变式一\n…")
    assert "### 变式一" in sheet and "--no-qwen 模式" not in sheet


def test_empty_recall_placeholder():
    sheet = pd_.build_drill_sheet("全新知识点", [], None)
    assert "无相似历史错题" in sheet


def test_cause_extraction():
    r = {"snippet": "科目：x\n错因：漏单调性\n状态：due", "score": 0.5, "metadata": {}}
    assert pd_._cause_of(r) == "漏单调性"


def test_cli_mutex_flag(index_dir, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["pre_drill.py", "--index", str(index_dir),
                                      "--qwen", "--no-qwen"])
    assert pd_.main() == 2


def test_cli_missing_index(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pd_, "REPO", tmp_path)  # 守卫以模块 REPO 为界，测试内重定向
    monkeypatch.setattr(sys, "argv", ["pre_drill.py", "--index", str(tmp_path / "nope"),
                                      "--no-qwen"])
    assert pd_.main() == 2
    assert "索引不存在" in capsys.readouterr().out


def test_cli_no_qwen_prints_sheet(index_dir, monkeypatch, capsys):
    monkeypatch.setattr(pd_, "REPO", index_dir.parent)
    monkeypatch.setattr(sys, "argv", ["pre_drill.py", "--index", str(index_dir),
                                      "--subject", "408-操作系统", "--topic", "死锁",
                                      "--no-qwen", "--fake"])
    assert pd_.main() == 0
    out = capsys.readouterr().out
    assert "考前预练卷" in out and "review:a" in out
