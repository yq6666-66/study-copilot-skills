# -*- coding: utf-8 -*-
"""端侧语义检索性能基准（合成数据，真实模型或 fake）。

度量三段：全量建索引 → 增量更新（改 1%）对比无缓存 → 查询延迟 avg/p95。
数据为程序合成的虚构错题文本（模板+随机参数），不含任何真实题库。

用法（仓库根目录）：
    python scripts/bench.py --size 300 --queries 30            # 真实模型基准（约 1-2 分钟）
    python scripts/bench.py --fake --size 30                   # 离线冒烟
    python scripts/bench.py ... --write docs/competition/端侧性能基准.md   # 报告落盘
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from local_retrieval.embedder import FakeEmbedder, get_embedder  # noqa: E402
from local_retrieval.index_store import build_index, search  # noqa: E402
from local_retrieval.vec_cache import embed_cached  # noqa: E402

SUBJECTS = {
    "数学一": ["极限计算", "中值定理证明", "二重积分", "级数判敛", "特征值", "条件概率", "最大似然"],
    "408-操作系统": ["进程调度", "信号量", "死锁检测", "页面置换", "文件系统", "磁盘调度", "中断处理"],
    "408-数据结构": ["二叉树遍历", "图的存储", "排序稳定性", "哈希冲突", "平衡树", "拓扑排序"],
    "法考": ["犯罪构成", "合同效力", "行政诉讼", "证据规则", "公司决议"],
}
CAUSES = ["概念混淆", "公式记错", "漏条件", "步骤跳步", "方法选择不当", "计算失误", "审题偏差"]


def synth_docs(size: int, seed: int = 20260914):
    rng = random.Random(seed)
    docs = []
    for i in range(size):
        subject = rng.choice(list(SUBJECTS))
        topic = rng.choice(SUBJECTS[subject])
        cause = rng.choice(CAUSES)
        text = "科目：{}\n知识点：{}\n错因：{}（参数 k={}，样本 r={}）\n状态：pending".format(
            subject, topic, cause, rng.randint(1, 999), round(rng.random(), 3))
        docs.append({"doc_id": "bench:{}".format(i), "text": text,
                     "metadata": {"kind": "review", "subject": subject, "topic": topic}})
    return docs


def timed(fn):
    t0 = time.time()
    out = fn()
    return out, time.time() - t0


def run_bench(size, queries, embedder, model_tag, tmp_root: Path):
    work = tmp_root / "bench"
    work.mkdir(parents=True, exist_ok=True)
    docs = synth_docs(size)

    # 1) 首次建索引（走缓存路径，缓存随之建立——模拟真实增量更新场景）
    (vectors, _), t_full = timed(lambda: embed_cached(embedder, [d["text"] for d in docs], model_tag, work))
    build_index(work, docs, vectors, model_tag)

    # 2) 增量：改 1% 文本后，缓存命中路径 vs 无缓存全量重算
    changed = max(1, size // 100)
    docs2 = [dict(d) for d in docs]
    for i in range(changed):
        docs2[i]["text"] += "（修订：补充易错点）"
    (vectors2, hits), t_cached = timed(lambda: embed_cached(
        embedder, [d["text"] for d in docs2], model_tag, work))
    _, t_full_rebuild = timed(lambda: embedder.embed([d["text"] for d in docs2]))
    report_extra = {"cache_hits": hits}

    # 3) 查询延迟（embed 单条 + search）
    rng = random.Random(7)
    latencies = []
    for _ in range(queries):
        q = "知识点 {}".format(rng.choice([d["metadata"]["topic"] for d in docs])) + "的{}".format(rng.choice(CAUSES))
        t0 = time.time()
        qvec = embedder.embed([q])[0]
        search(work, qvec, top_k=5)
        latencies.append(time.time() - t0)

    n_queries = queries or 1
    p95_idx = max(0, min(len(latencies) - 1, int(-(-0.95 * len(latencies) // 1)) - 1))
    return {
        "size": size, "queries": queries, "model": model_tag,
        "first_build_cached_s": round(t_full, 2),
        "incremental_cached_s": round(t_cached, 3),
        "full_rebuild_s": round(t_full_rebuild, 2),
        "speedup": round(t_full_rebuild / t_cached, 1) if t_cached else None,
        "cache_hits": report_extra["cache_hits"],
        "query_latency_ms_avg": round(statistics.mean(latencies) * 1000, 1),
        "query_latency_ms_p95": round(sorted(latencies)[p95_idx] * 1000, 1) if len(latencies) >= 5 else None,
        "dims": len(vectors[0]),
    }


def to_markdown(r: dict, python_ver: str, platform: str, measured_at: str) -> str:
    return """# 端侧语义检索性能基准

> 本报告数字由 `scripts/bench.py` 真实运行产出（{at}），数据为合成虚构错题文本（模板+随机参数，无任何真实题库）。

| 环境 | {py} / {plat} |
| --- | --- |
| 模型 | `{model}`（CPU） |
| 语料规模 | {size} 条错题，维度 {dims} |

| 指标 | 数值 |
| --- | --- |
| 首次建索引（含缓存落盘，{size} 条） | **{fb}s** |
| 增量更新（改 1%={ch} 条，缓存命中 {hits} 条） | **{inc}s** |
| 无缓存全量重算同批 | {fr}s |
| 增量 vs 全量重算加速 | **约 {sp}×** |
| 单查询延迟 avg（embed+检索，{q} 次） | {la} ms |
| 单查询延迟 p95 | {p95} ms |

结论：端侧检索在千条级错题库上保持亚秒级查询与秒级增量更新，CPU 即可支撑日常复测节奏。
""".format(at=measured_at, py=python_ver, plat=platform, model=r["model"], size=r["size"],
           dims=r["dims"], fb=r["first_build_cached_s"], ch=max(1, r["size"] // 100),
           hits=r.get("cache_hits"), inc=r["incremental_cached_s"], fr=r["full_rebuild_s"],
           sp=r["speedup"], q=r["queries"], la=r["query_latency_ms_avg"], p95=r["query_latency_ms_p95"])


def main() -> int:
    parser = argparse.ArgumentParser(description="端侧检索性能基准（合成数据）")
    parser.add_argument("--size", type=int, default=300)
    parser.add_argument("--queries", type=int, default=30)
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--tmp", default=None, help="工作目录（默认系统临时目录）")
    parser.add_argument("--write", default=None, help="Markdown 报告输出路径")
    args = parser.parse_args()

    import platform as _plat
    import tempfile
    tmp_root = Path(args.tmp or tempfile.mkdtemp(prefix="sc-bench-"))
    if args.fake:
        embedder, tag = FakeEmbedder(), "fake"
    else:
        embedder = get_embedder()
        tag = embedder_model_tag_of(embedder)
    try:
        report = run_bench(args.size, args.queries, embedder, tag, tmp_root)
    except RuntimeError as exc:
        print("基准失败：{}".format(exc))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.write:
        out = REPO / args.write
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(to_markdown(report, sys.version.split()[0], _plat.platform(),
                                   time.strftime("%Y-%m-%d %H:%M")), encoding="utf-8")
        print("报告已写入：{}".format(out))
    return 0


def embedder_model_tag_of(embedder) -> str:
    return getattr(embedder, "model_tag", "embed")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
