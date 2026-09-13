# -*- coding: utf-8 -*-
"""检索质量端到端测试：真实 bge-small-zh 模型下的跨科目召回。

需要本地已下载模型（python scripts/local_retrieval/download_model.py）。
CI / 无模型环境自动 skip，绝不在测试里触发下载。
"""
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

def _has_local_model() -> bool:
    models = REPO / "models"
    return models.exists() and any(models.rglob("*.onnx"))


_HAS_MODEL = _has_local_model()
_HAS_FASTEMBED = True
try:
    import fastembed  # noqa: F401
except ImportError:
    _HAS_FASTEMBED = False

pytestmark = pytest.mark.skipif(
    os.environ.get("CI") or not _HAS_MODEL or not _HAS_FASTEMBED,
    reason="需本地 bge-small-zh 模型（download_model.py 预下载）；CI 自动跳过",
)


@pytest.fixture(scope="module")
def real_index(tmp_path_factory):
    from local_retrieval.embed_index import incremental_vectors
    from local_retrieval.embedder import get_embedder
    from local_retrieval.corpus import collect
    from local_retrieval.index_store import build_index

    out = tmp_path_factory.mktemp("index")
    docs = collect(REPO / "demo-vault")
    assert docs, "demo-vault 语料为空"
    embedder = get_embedder()
    vectors, _ = incremental_vectors(embedder, docs, "real", out, use_cache=False)
    build_index(out, docs, vectors, "real")
    return out, docs


def test_deadlock_query_recalls_deadlock_note(real_index):
    from local_retrieval.index_store import search
    from local_retrieval.embedder import get_embedder
    out, _ = real_index
    qvec = get_embedder().embed(["进程死锁检测和银行家算法又算错了"])[0]
    results = search(out, qvec, top_k=3)
    assert results and "死锁" in results[0]["doc_id"]
    # 跨科目零串扰：top-3 不出现数学一条目
    assert all("数学" not in r["doc_id"] for r in results)


def test_series_query_recalls_series_note(real_index):
    from local_retrieval.index_store import search
    from local_retrieval.embedder import get_embedder
    out, _ = real_index
    qvec = get_embedder().embed(["级数收敛判别方法总是选错"])[0]
    results = search(out, qvec, top_k=3)
    assert results and "级数" in results[0]["doc_id"]
    assert all("操作系统" not in r["doc_id"] for r in results)
