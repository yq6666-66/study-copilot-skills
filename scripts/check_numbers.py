# -*- coding: utf-8 -*-
"""材料数字一致性门禁（第六道）：README（中/英）、证据总览、AI 技术实践说明中声明的
调用次数、模型分布、token 累计与留痕表行数，必须与真实留痕一致。

真值来源（双模式）：
- 本地：logs/qwen/ 全量留痕（同时校验仓库内脱敏索引与之一致，防索引漂移）；
- CI：无 logs/（gitignore）→ 退回仓库内 docs/competition/留痕索引.json
  （只含文件名/模型/token/时延/时间戳，不含请求与响应内容）。

用法：
    python scripts/check_numbers.py             # 校验
    python scripts/check_numbers.py --emit      # 从 logs/qwen/ 重新生成留痕索引
退出码 0 = 一致。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOG_DIR = REPO / "logs" / "qwen"
MANIFEST = REPO / "docs" / "competition" / "留痕索引.json"


def stats_from_logs(root: Path) -> dict:
    calls = tokens = 0
    by_model: dict = {}
    files = []
    for f in sorted((root / "logs" / "qwen").glob("*.json")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        calls += 1
        u = rec.get("usage") or {}
        tokens += u.get("total_tokens") or 0
        m = rec.get("model", "?")
        by_model[m] = by_model.get(m, 0) + 1
        files.append({"name": f.name, "model": m, "total_tokens": u.get("total_tokens"),
                      "latency_ms": rec.get("latency_ms"), "timestamp": rec.get("timestamp")})
    return {"calls": calls, "tokens": tokens, "by_model": by_model, "files": files}


def load_manifest(root: Path):
    p = root / MANIFEST.relative_to(REPO)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {"calls": data["calls"], "tokens": data["tokens"],
                "by_model": data["by_model"], "files": data.get("files", [])}
    except (json.JSONDecodeError, KeyError):
        return None


def truth(root: Path = REPO) -> dict:
    s = stats_from_logs(root)
    m = load_manifest(root)
    if s["calls"] == 0:
        return m or {"calls": 0, "tokens": 0, "by_model": {}, "files": []}
    return {**s, "_manifest_mismatch": (m is not None and (
        m["calls"] != s["calls"] or m["tokens"] != s["tokens"] or m["by_model"] != s["by_model"]))}


def emit_manifest(root: Path = REPO) -> int:
    s = stats_from_logs(root)
    if not s["calls"]:
        print("logs/qwen/ 无留痕，未生成索引")
        return 2
    doc = {"generated_from": "logs/qwen/", "note": "脱敏索引：仅文件名与用量，无请求/响应内容",
           "calls": s["calls"], "tokens": s["tokens"], "by_model": s["by_model"], "files": s["files"]}
    MANIFEST.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print("已生成 {}：{} 次 / {} tokens".format(MANIFEST.name, s["calls"], s["tokens"]))
    return 0


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def check(root: Path = REPO) -> list[str]:
    t = truth(root)
    bad: list[str] = []
    if t.get("_manifest_mismatch"):
        bad.append("留痕索引与 logs/qwen/ 实际统计不一致（请重跑 --emit）")

    def want(doc: str, pattern: str, expected, label: str, cast=int):
        m = re.search(pattern, doc)
        if not m:
            bad.append("{}: 未找到 {}".format(label, pattern[:40]))
            return
        got = cast(m.group(1).replace(",", ""))
        if got != expected:
            bad.append("{}: 声明 {}，实际应为 {}".format(label, got, expected))

    readme = _read(root / "README.md")
    want(readme, r"以下 \*\*(\d+) 次调用\*\*", t["calls"], "README.md 调用数")
    for model, n in t["by_model"].items():
        if "`{}` ×{}".format(model, n) not in readme:
            bad.append("README.md: 模型分布缺 {} ×{}".format(model, n))
    table_rows = len(re.findall(r"^\|\s*\d+\s*\|[^|]*\|[^|]*\|\s*`2026\d{4}-\d{6}`\s*\|\s*$", readme, re.M))
    if table_rows != t["calls"]:
        bad.append("README.md: 实录表 {} 行 ≠ 留痕 {} 份".format(table_rows, t["calls"]))

    en = _read(root / "docs" / "README.en.md")
    want(en, r"(\d+) real (?:requests|calls)", t["calls"], "README.en.md 调用数")

    ov = _read(root / "docs/competition/千问证据总览.md")
    want(ov, r"真实调用：\*\*(\d+) 次\*\*", t["calls"], "证据总览 调用数")
    want(ov, r"累计 token：\*\*([\d,]+)\*\*", t["tokens"], "证据总览 token 累计")
    detail_rows = len(re.findall(r"^\| 2026\d{2}-?\d{2}-?\d{2}[^|]*\|[^|]*\| \d+ \| \d+ \|$", ov, re.M))
    if detail_rows != t["calls"]:
        bad.append("证据总览: 明细表 {} 行 ≠ 留痕 {} 份".format(detail_rows, t["calls"]))

    prac = _read(root / "docs" / "competition/AI技术实践说明.md")
    want(prac, r"共 (\d+) 次真实调用全部留痕", t["calls"], "实践说明 调用数")
    want(prac, r"累计 ([\d,]+) tokens", t["tokens"], "实践说明 token 累计")
    return bad


def main() -> int:
    argv = sys.argv[1:]
    if "--emit" in argv:
        return emit_manifest()
    bad = check()
    t = truth()
    if bad:
        print("数字一致性不通过 {} 处：".format(len(bad)))
        for b in bad:
            print("  -", b)
        return 1
    print("OK：材料数字与留痕真值一致（{} 次 / {} tokens）".format(t["calls"], t["tokens"]))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
