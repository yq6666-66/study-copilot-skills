# -*- coding: utf-8 -*-
"""文档回引用路径校验：README.md 与 docs/ 内 Markdown 反引号中的"仓库路径"必须真实存在。

动机：qwen3.8-flash 生成的架构文档初稿曾把路径简写（漏 `local_retrieval/` 段）——
路径漂移对 AI 生成文档是系统性风险，用机器门禁固化防回归。

判定为"仓库路径引用"的条件（避免把模型名/概念路径/散文误报）：
- 反引号内含 `/`；不含占位符/空白/URL/`--` 参数；
- 首段是仓库顶层条目名（如 scripts、docs、plugins、demo-vault……）。
解析依次尝试：仓库根 → 当前文档目录 → plugins/study-copilot/ 简写 → 补 .py。

用法：python scripts/check_doc_paths.py [仓库根]
退出码 0 = 通过；1 = 有失效路径。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

INLINE_CODE = re.compile(r"`([^`\n]+)`")
SKIP_HINT = ("http", " ", "{", "*", "<", ">", "~", "://", "--")


def top_level_names(root: Path) -> set:
    return {p.name for p in root.iterdir() if not p.name.startswith(".") and p.name not in ("dist", "logs", "models")}


def repo_path_tokens(text: str, top: set) -> list[str]:
    out = []
    for token in INLINE_CODE.findall(text):
        token = token.strip().rstrip("/")
        if "/" not in token or any(h in token for h in SKIP_HINT) or token.startswith("-"):
            continue
        if token.split("/")[0] not in top:
            continue  # 非仓库顶层前缀：外部路径/安装位置/模型名等概念性引用
        out.append(token)
    return out


def resolve(token: str, doc_dir: Path, root: Path) -> bool:
    candidates = [root / token, doc_dir / token, root / "plugins/study-copilot" / token]
    for c in candidates:
        if c.exists():
            return True
    if not Path(token).suffix:
        for c in candidates:
            if Path(str(c) + ".py").exists():
                return True
    return False


def check(root: Path) -> list[str]:
    import subprocess
    tracked = set()
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, timeout=30)
        tracked = set(out.stdout.splitlines())
    except (OSError, subprocess.TimeoutExpired):
        pass  # 无 git 环境时退化为仅按存在性判断

    def is_gitignored(token: str) -> bool:
        if not tracked:
            return False
        prefix = token + "/"
        return not any(t == token or t.startswith(prefix) for t in tracked)

    top = top_level_names(root)
    bad = []
    for doc in [root / "README.md"] + sorted((root / "docs").rglob("*.md")):
        if not doc.exists():
            continue
        for token in repo_path_tokens(doc.read_text(encoding="utf-8", errors="ignore"), top):
            # 本地与 CI 一致：git 忽略的生成物路径（如索引目录）豁免存在性要求
            if is_gitignored(token):
                continue
            if not resolve(token, doc.parent, root):
                bad.append("{}: {}".format(doc.relative_to(root), token))
    return bad


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    bad = check(root)
    if bad:
        print("文档引用了 {} 个不存在的仓库路径：".format(len(bad)))
        for line in bad:
            print("  -", line)
        return 1
    print("OK：README 与 docs/ 中全部仓库路径引用真实存在")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
