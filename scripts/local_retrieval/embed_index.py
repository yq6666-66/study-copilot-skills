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
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from local_retrieval.corpus import collect
    from local_retrieval.embedder import MODEL_NAME, FakeEmbedder, get_embedder
    from local_retrieval.index_store import build_index
else:
    from .corpus import collect
    from .embedder import MODEL_NAME, FakeEmbedder, get_embedder
    from .index_store import build_index


def main() -> int:
    parser = argparse.ArgumentParser(description="为 Vault 语料建端侧向量索引（本地计算，不上传）")
    parser.add_argument("--corpus", default="demo-vault", help="语料根目录（默认 demo-vault）")
    parser.add_argument("--out", default=None, help="索引输出目录（默认 <corpus>/30-知识/.index）")
    parser.add_argument("--model", default=MODEL_NAME, help="embedding 模型名")
    parser.add_argument("--fake", action="store_true", help="用 FakeEmbedder 离线冒烟，不下载模型")
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

    embedder = FakeEmbedder() if args.fake else get_embedder(args.model)
    started = __import__("time").time()
    vectors = embedder.embed([d["text"] for d in docs])
    meta = build_index(out_dir, docs, vectors, "fake" if args.fake else args.model)
    elapsed = __import__("time").time() - started
    print("已建索引：{} 篇文档，维度 {}，输出 {}，耗时 {:.1f}s".format(
        meta["count"], meta["dim"], out_dir, elapsed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
