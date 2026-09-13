# -*- coding: utf-8 -*-
"""端侧语义检索离线单测：全部使用 FakeEmbedder 与 tmp_path，不下载模型、不联网。"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from local_retrieval import corpus as corpus_mod  # noqa: E402
from local_retrieval import index_store  # noqa: E402
from local_retrieval.embedder import FakeEmbedder  # noqa: E402

QUEUE = {
    "schemaVersion": "1.1",
    "recordType": "ReviewQueue",
    "generatedAt": "2026-09-13",
    "items": [
        {"id": "r001", "subject": "数学一", "topic": "级数", "errorCause": "判别法选择不当",
         "errorCauseStatus": "hypothesis", "nextRetestDate": None, "retestOffsetDays": 7,
         "status": "pending", "masteryEvidence": []},
        {"id": "r002", "subject": "408-操作系统", "topic": "死锁", "errorCause": "安全性检测漏分支",
         "errorCauseStatus": "confirmed", "nextRetestDate": "2026-09-14", "retestOffsetDays": None,
         "status": "retesting", "masteryEvidence": []},
    ],
}


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    qdir = tmp_path / "30-知识"
    qdir.mkdir(parents=True)
    (qdir / "错题队列.json").write_text(json.dumps(QUEUE, ensure_ascii=False), encoding="utf-8")
    note = tmp_path / "30-知识" / "错题笔记" / "408-操作系统"
    note.mkdir(parents=True)
    (note / "死锁簇.md").write_text("# 死锁簇\n\n银行家算法安全性检测笔记。", encoding="utf-8")
    return tmp_path


def test_collect_reads_queue_and_notes(vault: Path):
    docs = corpus_mod.collect(vault)
    ids = {d["doc_id"] for d in docs}
    assert "review:r001" in ids and "review:r002" in ids
    md_docs = [d for d in docs if d["doc_id"].startswith("md:")]
    assert len(md_docs) == 1
    assert md_docs[0]["metadata"]["subject"] == "408-操作系统"


def test_build_and_load_roundtrip(tmp_path: Path, vault: Path):
    docs = corpus_mod.collect(vault)
    embedder = FakeEmbedder(dim=16)
    vectors = embedder.embed([d["text"] for d in docs])
    out = tmp_path / ".index"
    meta = index_store.build_index(out, docs, vectors, "fake")
    assert meta["count"] == len(docs)
    vecs, loaded = index_store.load_index(out)
    assert vecs.shape == (len(docs), 16)
    assert loaded["model"] == "fake"


def test_search_returns_sorted_topk(tmp_path: Path, vault: Path):
    docs = corpus_mod.collect(vault)
    embedder = FakeEmbedder(dim=16)
    vectors = embedder.embed([d["text"] for d in docs])
    out = tmp_path / ".index"
    index_store.build_index(out, docs, vectors, "fake")

    qvec = embedder.embed([docs[0]["text"]])[0]
    results = index_store.search(out, qvec, top_k=2)
    assert 1 <= len(results) <= 2
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert all(-1.001 <= s <= 1.001 for s in scores)
    assert results[0]["doc_id"] == docs[0]["doc_id"]  # 自查询自最相似


def test_search_subject_filter(tmp_path: Path, vault: Path):
    docs = corpus_mod.collect(vault)
    embedder = FakeEmbedder(dim=16)
    vectors = embedder.embed([d["text"] for d in docs])
    out = tmp_path / ".index"
    index_store.build_index(out, docs, vectors, "fake")
    qvec = embedder.embed(["任意查询"])[0]
    results = index_store.search(out, qvec, top_k=10, subject="408-操作系统")
    assert results and all(r["metadata"]["subject"] == "408-操作系统" for r in results)


def test_search_skips_zero_norm_vectors(tmp_path: Path):
    docs = [{"doc_id": "d1", "text": "a", "metadata": {}},
            {"doc_id": "d2", "text": "b", "metadata": {}}]
    vectors = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]  # 一条零向量
    out = tmp_path / ".index"
    index_store.build_index(out, docs, vectors, "fake")
    results = index_store.search(out, [1.0, 0.0, 0.0], top_k=5)
    assert results[0]["doc_id"] == "d2"
