# -*- coding: utf-8 -*-
"""向量缓存：按 模型+文本 缓存 embedding 结果，重建索引只对新增/变更文本重新计算。

缓存文件 emb_cache.json 随索引目录存放，键为 "model|sha256(text)"：
- 同文本换模型不会命中旧缓存（键含模型名）；
- 缓存损坏时静默作废重建，不影响索引正确性。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Tuple

CACHE_FILE = "emb_cache.json"


def _key(model: str, text: str) -> str:
    return "{}|{}".format(model, hashlib.sha256(text.encode("utf-8")).hexdigest())


def load(out_dir: Path) -> Dict[str, List[float]]:
    p = out_dir / CACHE_FILE
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}  # 缓存损坏直接作废，下次重建即可


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
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / CACHE_FILE).write_text(json.dumps(cache), encoding="utf-8")

    vectors = [cache[k] for k in keys]
    return vectors, hits
