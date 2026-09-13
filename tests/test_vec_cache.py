# -*- coding: utf-8 -*-
"""向量缓存离线单测：FakeEmbedder + tmp_path，不触真实模型。"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from local_retrieval.vec_cache import CACHE_FILE, embed_cached, load  # noqa: E402


class CountingEmbedder:
    """记录被真实调用 embed 的文本条数。"""

    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += len(texts)
        return [[float(len(t)), 1.0, 0.0] for t in texts]


def test_first_build_no_hits(tmp_path: Path):
    emb = CountingEmbedder()
    vectors, hits = embed_cached(emb, ["甲", "乙"], "fake", tmp_path)
    assert hits == 0 and emb.calls == 2
    assert len(vectors) == 2


def test_rebuild_hits_and_skips_compute(tmp_path: Path):
    emb = CountingEmbedder()
    embed_cached(emb, ["甲", "乙"], "fake", tmp_path)
    before = emb.calls
    vectors2, hits2 = embed_cached(emb, ["甲", "乙"], "fake", tmp_path)
    assert hits2 == 2 and emb.calls == before  # 全命中，零重算
    assert vectors2[0][0] == 1.0  # len("甲") == 1


def test_partial_change_only_computes_new(tmp_path: Path):
    emb = CountingEmbedder()
    embed_cached(emb, ["甲", "乙"], "fake", tmp_path)
    before = emb.calls
    _, hits = embed_cached(emb, ["甲", "乙", "丙丁"], "fake", tmp_path)
    assert hits == 2 and emb.calls == before + 1


def test_model_namespace_isolation(tmp_path: Path):
    emb = CountingEmbedder()
    embed_cached(emb, ["甲"], "model-a", tmp_path)
    before = emb.calls
    _, hits = embed_cached(emb, ["甲"], "model-b", tmp_path)
    assert hits == 0 and emb.calls == before + 1  # 换模型不命中旧缓存


def test_duplicate_texts_embedded_once(tmp_path: Path):
    emb = CountingEmbedder()
    vectors, hits = embed_cached(emb, ["甲", "甲", "乙"], "fake", tmp_path)
    assert emb.calls == 2  # 去重后只算两种
    assert vectors[0] == vectors[1]


def test_corrupted_cache_treated_as_empty(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / CACHE_FILE).write_text("{损坏的json", encoding="utf-8")
    assert load(tmp_path) == {}
    emb = CountingEmbedder()
    _, hits = embed_cached(emb, ["甲"], "fake", tmp_path)
    assert hits == 0 and emb.calls == 1
    assert load(tmp_path)  # 重建后缓存恢复可用


def test_legacy_json_migrates_to_npz(tmp_path: Path):
    """旧版 emb_cache.json 可读，且写入时迁移为 npz 并删除 json。"""
    import json as _json
    from local_retrieval.vec_cache import CACHE_FILE as NPZ_NAME, _key, LEGACY_JSON

    tmp_path.mkdir(parents=True, exist_ok=True)
    legacy = {str(_key("fake", "甲")): [1.0, 2.0, 0.0]}  # 与 embedder 输出同维
    (tmp_path / LEGACY_JSON).write_text(_json.dumps(legacy), encoding="utf-8")
    emb = CountingEmbedder()
    vectors, hits = embed_cached(emb, ["甲", "乙"], "fake", tmp_path)
    assert hits == 1 and emb.calls == 1
    assert (tmp_path / NPZ_NAME).exists()
    assert not (tmp_path / LEGACY_JSON).exists()  # 已迁移删除
    assert vectors[0] == [1.0, 2.0, 0.0]


def test_long_keys_not_truncated(tmp_path: Path):
    """npz key 变长不截断（模型名+64hex 超过 64 字符）。"""
    emb = CountingEmbedder()
    model = "BAAI/bge-small-zh-v1.5"
    texts = ["文本{}".format(i) for i in range(5)]
    v1, _ = embed_cached(emb, texts, model, tmp_path)
    v2, hits = embed_cached(CountingEmbedder(), texts, model, tmp_path)
    assert hits == 5
    assert v1 == v2  # roundtrip 无损
