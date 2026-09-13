# -*- coding: utf-8 -*-
"""端侧语义检索查询。

用法（仓库根目录下运行）：
    python scripts/local_retrieval/semantic_search.py --query "级数判别 总是错" --top-k 5
    python scripts/local_retrieval/semantic_search.py --query "死锁" --subject 408-操作系统
    python scripts/local_retrieval/semantic_search.py --query "测试" --fake
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from local_retrieval.embedder import MODEL_NAME, FakeEmbedder, get_embedder
    from local_retrieval.index_store import search
else:
    from .embedder import MODEL_NAME, FakeEmbedder, get_embedder
    from .index_store import search


def main() -> int:
    parser = argparse.ArgumentParser(description="端侧语义检索（本地计算，结果 JSON 输出）")
    parser.add_argument("--index", default=None, help="索引目录（默认 demo-vault/30-知识/.index）")
    parser.add_argument("--query", required=True, help="自然语言查询")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--subject", default=None, help="按科目过滤，如 408-操作系统")
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--fake", action="store_true", help="用 FakeEmbedder 离线冒烟")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    index_dir = Path(args.index) if args.index else root / "demo-vault" / "30-知识" / ".index"
    if not (index_dir / "meta.json").exists():
        print("索引不存在：{}\n先建一次索引：python scripts/local_retrieval/embed_index.py".format(index_dir))
        return 1

    embedder = FakeEmbedder() if args.fake else None
    if embedder is None:
        try:
            embedder = get_embedder(args.model)
        except RuntimeError as exc:  # 模型未就绪时给下载指引，不抛 traceback
            print(str(exc))
            return 2
    qvec = embedder.embed([args.query])[0]
    results = search(index_dir, qvec, top_k=args.top_k, subject=args.subject)
    print(json.dumps({"query": args.query, "subject_filter": args.subject,
                      "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
