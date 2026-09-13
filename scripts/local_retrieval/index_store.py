# -*- coding: utf-8 -*-
"""索引仓库：向量与元数据落盘/加载/检索的纯逻辑，供 CLI 与测试复用。"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

VECTORS_FILE = "vectors.npy"
META_FILE = "meta.json"


def build_index(out_dir: Path, docs: List[Dict], vectors: List[List[float]], model_name: str) -> Dict:
    if len(docs) != len(vectors):
        raise ValueError("docs 与 vectors 数量不一致：{} vs {}".format(len(docs), len(vectors)))
    out_dir.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(vectors, dtype=np.float32)
    np.save(out_dir / VECTORS_FILE, arr)
    meta = {
        "model": model_name,
        "dim": int(arr.shape[1]) if arr.ndim == 2 else 0,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "count": len(docs),
        "docs": docs,
    }
    (out_dir / META_FILE).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def load_index(index_dir: Path):
    vecs = np.load(index_dir / VECTORS_FILE)
    meta = json.loads((index_dir / META_FILE).read_text(encoding="utf-8"))
    return vecs, meta


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


def search(index_dir: Path, query_vector: List[float], top_k: int = 5,
           subject: Optional[str] = None) -> List[Dict]:
    """余弦相似度检索。subject 过滤是对 metadata.subject 的相等匹配。"""
    vecs, meta = load_index(index_dir)
    q = _normalize(np.asarray(query_vector, dtype=np.float32))
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    scores = (vecs / norms) @ q
    order = np.argsort(-scores)
    results: List[Dict] = []
    for idx in order:
        doc = meta["docs"][int(idx)]
        if subject and doc.get("metadata", {}).get("subject") != subject:
            continue
        results.append(
            {
                "doc_id": doc["doc_id"],
                "score": round(float(scores[int(idx)]), 4),
                "metadata": doc.get("metadata", {}),
                "snippet": doc["text"][:120],
            }
        )
        if len(results) >= top_k:
            break
    return results
