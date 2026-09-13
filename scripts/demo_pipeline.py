# -*- coding: utf-8 -*-
"""学习副驾 · 一键端云协同演示管道。

端侧（本地 bge-small-zh 语义检索相似历史错题）→ 云端（DashScope Qwen 生成原创变式题）
→ 留痕总结，把「端云协同」浓缩成一条命令，供演示与评委复现。

用法（仓库根目录）：
    python scripts/demo_pipeline.py                 # 完整链路（真实模型 + 真实 Qwen 调用留痕）
    python scripts/demo_pipeline.py --item r028     # 指定错题条目
    python scripts/demo_pipeline.py --dry-cloud     # 只预览云端 prompt，不调用 API（离线演示）
    python scripts/demo_pipeline.py --fake          # 端侧用 FakeEmbedder 冒烟（不加载模型）

核心函数 run_pipeline 支持注入 embedder / chat，测试完全离线。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from local_retrieval.corpus import collect, _review_text  # noqa: E402
from local_retrieval.index_store import META_FILE, build_index, load_index, search  # noqa: E402

QUEUE_REL = Path("30-知识") / "错题队列.json"


def pick_item(items, item_id=None):
    """默认取第一条 retesting（临期复测最适合演示），退而 due，再退第一条。"""
    if item_id:
        for it in items:
            if it.get("id") == item_id:
                return it
        raise KeyError("找不到错题条目: {}".format(item_id))
    for status in ("retesting", "due"):
        for it in items:
            if it.get("status") == status:
                return it
    return items[0]


def _default_chat(messages, model="qwen-flash"):
    from qwen_engine import call_qwen
    return call_qwen(messages, model=model)


def ensure_index(embedder, corpus_dir, index_dir, model_tag):
    docs = collect(corpus_dir)
    if not docs:
        raise FileNotFoundError("语料为空: {}".format(corpus_dir))
    vectors = embedder.embed([d["text"] for d in docs])
    build_index(index_dir, docs, vectors, model_tag)
    return docs


def run_pipeline(corpus_dir, index_dir=None, item_id=None, embedder=None, chat=None,
                 dry_cloud=False, top_k=5):
    """执行端云协同演示，返回步骤报告 dict。"""
    from local_retrieval.embedder import FakeEmbedder
    corpus_dir = Path(corpus_dir)
    index_dir = Path(index_dir) if index_dir else corpus_dir / "30-知识" / ".index"
    embedder = embedder or FakeEmbedder()
    report = {"steps": []}

    # 步骤 1：端侧建/载索引（模型与索引不匹配时自动重建，防止跨模型维度/语义错配）
    t0 = time.time()
    model_tag = getattr(embedder, "model_tag", "embed")
    rebuilt = False
    if (index_dir / META_FILE).exists():
        meta = json.loads((index_dir / META_FILE).read_text(encoding="utf-8"))
        if meta.get("model") != model_tag:
            docs = ensure_index(embedder, corpus_dir, index_dir, model_tag)
            rebuilt = True
        else:
            docs = meta["docs"]
    else:
        docs = ensure_index(embedder, corpus_dir, index_dir, model_tag)
        rebuilt = True
    report["steps"].append({"step": "端侧索引", "docs": len(docs), "rebuilt": rebuilt,
                            "seconds": round(time.time() - t0, 2)})

    # 步骤 2：选定错题
    queue = json.loads((corpus_dir / QUEUE_REL).read_text(encoding="utf-8"))
    item = pick_item(queue["items"], item_id)
    report["item"] = {k: item.get(k) for k in ("id", "subject", "topic", "errorCause", "status")}

    # 步骤 3：端侧语义召回相似历史错题（排除自身）
    t1 = time.time()
    qvec = embedder.embed([_review_text(item)])[0]
    recalled = [r for r in search(index_dir, qvec, top_k=top_k + 1)
                if r["doc_id"] != "review:{}".format(item.get("id"))][:top_k]
    report["recalled"] = [{"doc_id": r["doc_id"], "score": r["score"],
                           "topic": r["metadata"].get("topic")} for r in recalled]
    report["steps"].append({"step": "端侧检索", "top_k": top_k, "seconds": round(time.time() - t1, 2)})

    # 步骤 4：云端 Qwen 变式出题（或 dry 预览）
    similar = "、".join(filter(None, (r["metadata"].get("topic") for r in recalled)))
    messages = [
        {"role": "system", "content": "你是考研陪练教练，只输出原创变式题，不复制任何真题。"},
        {"role": "user", "content": (
            "错因：{}（状态 {}，知识点 {}，科目 {}）。相似历史错题知识点：{}。"
            "请针对该错因出一道原创变式题：题目、答案、三步解析、一个陷阱说明。").format(
                item.get("errorCause"), item.get("errorCauseStatus"), item.get("topic"),
                item.get("subject"), similar or "无")},
    ]
    t2 = time.time()
    if dry_cloud:
        report["cloud"] = {"mode": "dry-preview", "prompt": messages[1]["content"]}
    else:
        result = (chat or _default_chat)(messages)
        report["cloud"] = {"mode": "live", "content": result["content"][:600],
                           "full_length": len(result["content"]),
                           "usage": result.get("usage"), "log_path": result.get("log_path"),
                           "model": result.get("model")}
    report["steps"].append({"step": "云端 Qwen" if not dry_cloud else "云端预览",
                            "seconds": round(time.time() - t2, 2)})
    return report


def print_human(report: dict) -> None:
    it = report["item"]
    for s in report["steps"]:
        extra = "（{} 篇）".format(s["docs"]) if "docs" in s else \
                ("（Top-{} 召回）".format(s["top_k"]) if "top_k" in s else "")
        print("▶ {}{}：{:.2f}s".format(s["step"], extra, s["seconds"]))
    print("\n[演示锚点] {} {}｜{}｜错因：{}（{}）".format(
        it["subject"], it["id"], it["topic"], it["errorCause"], it["status"]))
    print("[端侧检索] 相似历史错题：")
    for r in report["recalled"]:
        print("   {:<46} {:.3f}".format(r["doc_id"], r["score"]))
    c = report["cloud"]
    if c["mode"] == "dry-preview":
        print("\n[云端预览·未调用] prompt 节选：")
        print("   " + c["prompt"][:160] + "…")
    else:
        print("\n[Qwen生成] {}｜tokens={}｜留痕：{}".format(
            c.get("model"), (c.get("usage") or {}).get("total_tokens"), c.get("log_path")))
        print(c["content"][:400] + ("…（截断）" if c["full_length"] > 400 else ""))
    print("\n结论：端侧召回 × 云端生成 × 本地留痕 = 端云协同，数据不出域。")


def main() -> int:
    parser = argparse.ArgumentParser(description="一键端云协同演示管道")
    parser.add_argument("--corpus", default=str(REPO / "demo-vault"))
    parser.add_argument("--index", default=None)
    parser.add_argument("--item", default=None, help="错题 id（默认取第一条 retesting）")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--fake", action="store_true", help="端侧 FakeEmbedder 冒烟")
    parser.add_argument("--dry-cloud", action="store_true", help="只预览 prompt，不调用 Qwen")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON 报告")
    args = parser.parse_args()

    from local_retrieval.embedder import FakeEmbedder, get_embedder
    embedder = FakeEmbedder() if args.fake else get_embedder()
    try:
        report = run_pipeline(args.corpus, args.index, args.item, embedder,
                              dry_cloud=args.dry_cloud, top_k=args.top_k)
    except (FileNotFoundError, KeyError) as exc:
        print("演示失败：{}".format(exc))
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
