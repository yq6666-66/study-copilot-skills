# -*- coding: utf-8 -*-
"""建端侧语义索引。

用法（仓库根目录下运行）：
    python scripts/local_retrieval/embed_index.py                # 真实模型
    python scripts/local_retrieval/embed_index.py --fake         # 离线冒烟
    python scripts/local_retrieval/embed_index.py --corpus demo-vault --out demo-vault/30-知识/.index
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from local_retrieval.corpus import collect
    from local_retrieval.embedder import MODEL_NAME, FakeEmbedder, get_embedder
    from local_retrieval.index_store import build_index, load_index
    from local_retrieval.vec_cache import embed_cached
else:
    from .corpus import collect
    from .embedder import MODEL_NAME, FakeEmbedder, get_embedder
    from .index_store import build_index, load_index
    from .vec_cache import embed_cached


def incremental_vectors(embedder, docs, model_tag, out_dir, use_cache=True):
    """真增量：与旧索引比对，doc_id+文本均未变的条目直接复用旧向量（零 embed），
    只对新增/变更文本计算。返回 (与 docs 同序的向量, 复用条数)。"""
    from local_retrieval.index_store import META_FILE, VECTORS_FILE
    if not (out_dir / META_FILE).exists() or not (out_dir / VECTORS_FILE).exists():
        old_map = {}
    else:
        old_vecs, old_meta = load_index(out_dir)
        old_map = {d["doc_id"]: (d["text"], list(v)) for d, v in zip(old_meta["docs"], old_vecs)}

    vectors = [None] * len(docs)
    todo_idx = []
    reused = 0
    for i, d in enumerate(docs):
        prev = old_map.get(d["doc_id"])
        if prev is not None and prev[0] == d["text"]:
            vectors[i] = prev[1]
            reused += 1
        else:
            todo_idx.append(i)
    if todo_idx:
        texts = [docs[i]["text"] for i in todo_idx]
        if use_cache:
            new_vecs, _ = embed_cached(embedder, texts, model_tag, out_dir)
        else:
            new_vecs = embedder.embed(texts)
        for i, v in zip(todo_idx, new_vecs):
            vectors[i] = list(v)
    return vectors, reused


def main() -> int:
    parser = argparse.ArgumentParser(description="为 Vault 语料建端侧向量索引（本地计算，不上传）")
    parser.add_argument("--corpus", default="demo-vault", help="语料根目录（默认 demo-vault）")
    parser.add_argument("--out", default=None, help="索引输出目录（默认 <corpus>/30-知识/.index）")
    parser.add_argument("--model", default=MODEL_NAME, help="embedding 模型名")
    parser.add_argument("--fake", action="store_true", help="用 FakeEmbedder 离线冒烟，不下载模型")
    parser.add_argument("--no-cache", action="store_true",
                        help="禁用向量缓存，全部文本重新计算")
    parser.add_argument("--incremental", action="store_true",
                        help="与旧索引比对，未变条目直接复用向量（零计算）")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    corpus_dir = Path(args.corpus)
    if not corpus_dir.is_absolute():
        corpus_dir = root / corpus_dir
    out_dir = Path(args.out) if args.out else corpus_dir / "30-知识" / ".index"

    docs = collect(corpus_dir)
    if not docs:
        print("未采集到语料：{}".format(corpus_dir))
        return 1

    embedder = FakeEmbedder() if args.fake else None
    if embedder is None:
        try:
            embedder = get_embedder(args.model)
        except RuntimeError as exc:  # 依赖缺失/模型不可用 → 给出可操作指引而非 traceback
            print(str(exc))
            return 2
    started = time.time()
    texts = [d["text"] for d in docs]
    # fake 与真实模型用不同缓存命名空间，互不污染
    model_tag = "fake" if args.fake else args.model
    reused = 0
    if args.incremental:
        vectors, reused = incremental_vectors(
            embedder, docs, model_tag, out_dir, use_cache=not args.no_cache)
    elif args.no_cache:
        vectors = embedder.embed(texts)
    else:
        vectors, _hits = embed_cached(embedder, texts, model_tag, out_dir)
    meta = build_index(out_dir, docs, vectors, model_tag)
    elapsed = time.time() - started
    extra = "，增量复用 {}，重算 {}".format(reused, meta["count"] - reused) if args.incremental else ""
    print("已建索引：{} 篇文档，维度 {}，输出 {}，耗时 {:.1f}s{}".format(
        meta["count"], meta["dim"], out_dir, elapsed, extra))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
