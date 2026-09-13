# -*- coding: utf-8 -*-
"""向量缓存：按 模型+文本 缓存 embedding 结果，重建索引只对新增/变更文本重新计算。

存储格式：npz 二进制（keys + 二维 float32 矩阵）。
- 旧版 emb_cache.json（JSON 序列化）自动读取并迁移为 npz；
- 键含模型名：同文本换模型不会命中旧缓存；
- 缓存损坏时静默作废重建，不影响索引正确性。

性能注记（bench.py 实测驱动的设计修正）：小规模下 JSON 序列化的开销会超过
跳过的 embedding 计算（300 条 512 维实测为负加速），故改用二进制格式。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

CACHE_FILE = "emb_cache.npz"
LEGACY_JSON = "emb_cache.json"


def _key(model: str, text: str) -> str:
    return "{}|{}".format(model, hashlib.sha256(text.encode("utf-8")).hexdigest())


def load(out_dir: Path) -> Dict[str, List[float]]:
    npz = out_dir / CACHE_FILE
    if npz.exists():
        try:
            with np.load(npz, allow_pickle=False) as d:
                keys, vecs = list(d["keys"]), d["vecs"]
            return {str(k): [float(x) for x in v] for k, v in zip(keys, vecs)}
        except (OSError, KeyError, ValueError):
            return {}
    legacy = out_dir / LEGACY_JSON  # 旧版迁移（一次性）
    if legacy.exists():
        try:
            data = json.loads(legacy.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save(out_dir: Path, cache: Dict[str, List[float]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = list(cache.keys())
    if not keys:
        return
    vecs = np.asarray([cache[k] for k in keys], dtype=np.float32)
    np.savez_compressed(out_dir / CACHE_FILE, keys=np.asarray(keys), vecs=vecs)
    (out_dir / LEGACY_JSON).unlink(missing_ok=True)  # 迁移后删除旧文件


def embed_cached(embedder, texts: List[str], model: str, out_dir: Path) -> Tuple[List[List[float]], int]:
    """带缓存的批量 embedding。

    返回 (与 texts 同序的向量列表, 命中缓存的条数)。
    只对未命中的文本调用 embedder；有新增时整体落盘缓存。
    """
    cache = load(out_dir)
    keys = [_key(model, t) for t in texts]

    todo: List[str] = []
    todo_keys: List[str] = []
    seen = set()
    for t, k in zip(texts, keys):
        if k in cache or k in seen:
            continue
        seen.add(k)
        todo.append(t)
        todo_keys.append(k)

    hits = sum(1 for k in keys if k in cache)
    if todo:
        for k, vec in zip(todo_keys, embedder.embed(todo)):
            cache[k] = list(vec)
        _save(out_dir, cache)

    vectors = [cache[k] for k in keys]
    return vectors, hits
