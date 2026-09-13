# -*- coding: utf-8 -*-
"""check_doc_paths 单测。

说明：真实仓库的完整门禁（含 git ls-files 豁免）在 CI 的 checkout 环境直接执行；
此处用 tmp_path（无 git）专测判定与豁免规则的行为。
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from check_doc_paths import check  # noqa: E402


def _fake_repo(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "real.py").write_text("", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    return tmp_path


def test_missing_repo_path_detected(tmp_path):
    _fake_repo(tmp_path)
    (tmp_path / "README.md").write_text("入口 `scripts/ghost.py` 与 `docs` 无关", encoding="utf-8")
    bad = check(tmp_path)
    assert any("ghost.py" in b for b in bad)


def test_good_paths_and_suffixes_pass(tmp_path):
    _fake_repo(tmp_path)
    (tmp_path / "README.md").write_text(
        "`scripts/real.py` 全路径；`scripts/real` 省略扩展名补 .py 命中；`demo-vault` 无斜杠视为散文不检查",
        encoding="utf-8")
    assert check(tmp_path) == []


def test_non_repo_prefixes_exempt(tmp_path):
    _fake_repo(tmp_path)
    (tmp_path / "README.md").write_text(
        "外部路径 `~/.claude/skills/<name>`、模型 `BAAI/bge-small-zh-v1.5`、"
        "概念 `target_root/.marker` 均不检查",
        encoding="utf-8")
    assert check(tmp_path) == []
