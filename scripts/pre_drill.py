# -*- coding: utf-8 -*-
"""考前预练 CLI：端侧语义召回 → 云端 Qwen 定向变式题，一条命令串三引擎。

流程：
1. 用 --subject/--topic 组成查询，在本地向量索引（bge-small-zh）召回相似历史错题；
2. 把召回条目的错因/知识点交给云端 Qwen，生成**定向变式预练卷**（真实调用留痕）；
3. 输出 Markdown 预练卷：召回依据（带相似度）+ 变式题；--no-qwen 时只输出召回依据与本地模板题面。

安全：文件 I/O 仅 main() 内联守卫（禁 '..' + 限仓库目录）；核心函数只收数据；
Qwen 提示词约束：只基于给定错因出题、不复制原题面、不虚构召回之外的事实。

CLI：
    python scripts/pre_drill.py --index demo-vault/30-知识/.index --subject 408-操作系统 --topic 死锁 --qwen
    python scripts/pre_drill.py --index ... --subject 数学一 --topic 级数 --no-qwen --out dist/预练.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from local_retrieval.index_store import META_FILE, search  # noqa: E402


def recall(index_dir: Path, embedder, query: str, top_k: int = 5,
           subject: str | None = None) -> list[dict]:
    """端侧语义召回相似历史错题。"""
    qvec = embedder.embed([query])[0]
    return search(index_dir, qvec, top_k=top_k, subject=subject)


def qwen_drill(recalled: list[dict], query: str, model: str = "qwen-flash") -> str:
    """云端 Qwen 基于召回错因生成定向变式预练卷（真实调用留痕）。"""
    from qwen_engine import call_qwen
    causes = [{"topic": r["metadata"].get("topic"), "errorCause": _cause_of(r),
               "score": r["score"]} for r in recalled]
    result = call_qwen([
        {"role": "system", "content": (
            "你是考前陪练教练。仅基于给定错因清单出 3 道定向变式题，Markdown 输出；"
            "每题标注针对的错因；严禁复制原题面；不得虚构清单之外的事实。")},
        {"role": "user", "content": json.dumps(
            {"query": query, "causes": causes}, ensure_ascii=False)},
    ], model=model)
    return result["content"].strip()


def _cause_of(r: dict) -> str:
    snippet = r.get("snippet", "")
    for line in snippet.splitlines():
        if line.startswith("错因："):
            return line[len("错因："):]
    body = snippet
    if body.startswith("---"):  # 剥离 Markdown frontmatter 后再摘首行
        parts = body.split("---", 2)
        body = parts[2] if len(parts) > 2 else body
    first = next((ln.strip() for ln in body.splitlines()
                  if ln.strip() and not ln.startswith("#")), "")
    return first[:60] or snippet[:60]


def build_drill_sheet(query: str, recalled: list[dict], drill_md: str | None) -> str:
    lines = ["# 考前预练卷", "",
             "**预练目标**：{}".format(query), "",
             "## 端侧召回依据（本地 bge-small-zh）", ""]
    if recalled:
        for r in recalled:
            lines.append("- `{}` 相似度 {:.3f} ｜ {} ｜ 错因：{}".format(
                r["doc_id"], r["score"], r["metadata"].get("topic", "?"), _cause_of(r)))
    else:
        lines.append("- （索引中无相似历史错题：本次为全新知识点预练）")
    lines += ["", "## 定向变式题", ""]
    lines.append(drill_md if drill_md else
                 "（--no-qwen 模式：请依据上方错因自行组题，或加 --qwen 由云端生成并留痕）")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="考前预练：端侧召回 + 云端定向变式")
    parser.add_argument("--index", required=True, help="向量索引目录（.index）")
    parser.add_argument("--subject", default=None, help="按科目过滤召回")
    parser.add_argument("--topic", nargs="+", default=[], help="知识点/查询文本（可多词）")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--qwen", action="store_true", help="云端 Qwen 生成变式题（真实留痕）")
    parser.add_argument("--no-qwen", action="store_true", help="仅输出召回依据与本地模板")
    parser.add_argument("--out", default=None, help="输出 Markdown 路径（默认打印）")
    parser.add_argument("--fake", action="store_true", help="FakeEmbedder 离线冒烟")
    args = parser.parse_args()
    if args.qwen and args.no_qwen:
        print("--qwen 与 --no-qwen 互斥")
        return 2

    # 内联路径守卫（本模块唯一接触文件处）
    raws = [args.index] + ([args.out] if args.out else [])
    for raw in raws:
        if ".." in Path(raw).parts:
            print("路径不允许包含 '..' 段：{}".format(raw))
            return 2
    index_dir = Path(args.index).resolve()
    out_path = Path(args.out).resolve() if args.out else None
    for p in [index_dir] + ([out_path] if out_path else []):
        if p != REPO and REPO not in p.parents:
            print("路径必须位于仓库目录内：{}".format(p))
            return 2
    if not (index_dir / META_FILE).exists():
        print("索引不存在：{}（先运行 embed_index.py）".format(index_dir))
        return 2

    from local_retrieval.embedder import FakeEmbedder, get_embedder
    embedder = FakeEmbedder() if args.fake else get_embedder()
    query = " ".join(filter(None, [args.subject, " ".join(args.topic)])) or "综合"
    recalled = recall(index_dir, embedder, query, args.top_k, args.subject)
    drill_md = qwen_drill(recalled, query) if args.qwen else None
    sheet = build_drill_sheet(query, recalled, drill_md)

    if out_path:
        parent = out_path.parent
        if not parent.is_dir():
            parent.mkdir(exist_ok=True)
        out_path.write_text(sheet, encoding="utf-8")
        print("预练卷已写入 → {}".format(out_path))
    else:
        print(sheet)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
