# -*- coding: utf-8 -*-
"""增量索引离线单测（FakeEmbedder + tmp_path）。"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from local_retrieval.embed_index import incremental_vectors  # noqa: E402
from local_retrieval.embedder import FakeEmbedder  # noqa: E402
from local_retrieval.index_store import build_index, load_index  # noqa: E402


class CountingEmbedder:
    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += len(texts)
        return FakeEmbedder().embed(texts)


def _doc(i, text):
    return {"doc_id": "d{}".format(i), "text": text, "metadata": {}}


def test_incremental_reuses_unchanged_and_embeds_only_new(tmp_path):
    emb = CountingEmbedder()
    docs1 = [_doc(1, "甲"), _doc(2, "乙")]
    v1, _ = incremental_vectors(emb, docs1, "fake", tmp_path, use_cache=False)
    build_index(tmp_path, docs1, v1, "fake")
    calls_after_first = emb.calls

    # 第二次：d1 不变、d2 改文本、新增 d3
    docs2 = [_doc(1, "甲"), _doc(2, "乙改"), _doc(3, "丙")]
    v2, reused = incremental_vectors(emb, docs2, "fake", tmp_path, use_cache=False)
    assert reused == 1
    assert emb.calls - calls_after_first == 2  # 只算 d2(新文本)+d3

    # 未变条目向量与旧值逐位一致
    assert v2[0] == v1[0]


def test_incremental_order_and_deletion(tmp_path):
    emb = CountingEmbedder()
    docs = [_doc(1, "甲"), _doc(2, "乙"), _doc(3, "丙")]
    v, _ = incremental_vectors(emb, docs, "fake", tmp_path, use_cache=False)
    build_index(tmp_path, docs, v, "fake")

    docs2 = [_doc(3, "丙"), _doc(1, "甲")]  # 删除 d2、打乱顺序
    v2, reused = incremental_vectors(emb, docs2, "fake", tmp_path, use_cache=False)
    assert reused == 2 and emb.calls == 3  # 无新计算
    old_map = {d["doc_id"]: vec for d, vec in zip(docs, v)}
    assert v2[0] == old_map["d3"] and v2[1] == old_map["d1"]
    meta = build_index(tmp_path, docs2, v2, "fake")
    vecs, loaded = load_index(tmp_path)
    assert loaded["count"] == 2
    assert [d["doc_id"] for d in loaded["docs"]] == ["d3", "d1"]


def test_incremental_without_old_index_falls_back(tmp_path):
    emb = CountingEmbedder()
    docs = [_doc(1, "甲")]
    v, reused = incremental_vectors(emb, docs, "fake", tmp_path, use_cache=False)
    assert reused == 0 and emb.calls == 1
    assert len(v) == 1
