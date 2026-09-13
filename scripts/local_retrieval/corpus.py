# -*- coding: utf-8 -*-
"""语料采集：错题队列 JSON + Vault Markdown。

采集约定：
- 错题队列（30-知识/错题队列.json）：ReviewQueue 1.1，每条 item 一篇文档，
  doc_id 形如 review:r001，metadata 携带 subject/topic/source_path。
- Markdown：corpus 目录下所有 .md（跳过 .index 内部文件），doc_id 形如 md:<相对路径>。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

QUEUE_RELPATH = Path("30-知识") / "错题队列.json"


def _review_text(item: dict) -> str:
    evidence = "；".join(item.get("masteryEvidence") or [])
    return (
        "科目：{}\n知识点：{}\n错因：{}\n状态：{}\n掌握证据：{}".format(
            item.get("subject"),
            item.get("topic"),
            item.get("errorCause"),
            item.get("status"),
            evidence or "（暂无）",
        )
    )


def _guess_subject(md_path: Path, text: str) -> str | None:
    for part in md_path.parts:
        if "408" in part or "操作系统" in part:
            return "408-操作系统"
        if "数学" in part:
            return "数学一"
        if "英语" in part:
            return "英语一"
    for keyword, subject in (("操作系统", "408-操作系统"), ("408", "408-操作系统"), ("数学", "数学一")):
        if keyword in text[:400]:
            return subject
    return None


def collect(corpus_dir: Path) -> List[Dict]:
    """返回文档列表：[{doc_id, text, metadata}]。corpus_dir 不存在时返回空列表。"""
    docs: List[Dict] = []
    queue = corpus_dir / QUEUE_RELPATH
    if queue.exists():
        try:
            data = json.loads(queue.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = None  # 队列损坏不阻塞其余语料采集（qwen3.8-flash 审查意见#3）
        if isinstance(data, dict):
            seen_ids = set()
            for i, item in enumerate(data.get("items", [])):
                doc_id = "review:{}".format(item.get("id") or i)  # None/空 id 兜底（审查意见#4）
                if doc_id in seen_ids:
                    doc_id = "review:{}-{}".format(item.get("id") or i, i)
                seen_ids.add(doc_id)
                docs.append(
                    {
                        "doc_id": doc_id,
                        "text": _review_text(item),
                        "metadata": {
                            "kind": "review",
                            "subject": item.get("subject"),
                            "topic": item.get("topic"),
                            "status": item.get("status"),
                            "source_path": str(queue),
                        },
                    }
                )
    for md in sorted(corpus_dir.rglob("*.md")):
        if ".index" in md.parts:
            continue
        text = md.read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            continue
        docs.append(
            {
                "doc_id": "md:" + md.relative_to(corpus_dir).as_posix(),
                "text": text[:2000],
                "metadata": {
                    "kind": "note",
                    "subject": _guess_subject(md, text),
                    "topic": md.stem,
                    "source_path": str(md),
                },
            }
        )
    return docs
