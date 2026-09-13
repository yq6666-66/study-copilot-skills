# -*- coding: utf-8 -*-
"""安装器离线单测：全部基于 tmp_path，绝不写真实用户主目录。"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import install  # noqa: E402


def test_list_skills_nonempty():
    skills = install.list_skills()
    assert "kaoyan-error-loop-coach" in skills
    assert "kaoyan-qwen-drill" in skills  # 新增 Skill 也能被发现
    assert len(skills) >= 14


def test_install_claude_code(tmp_path: Path):
    installed = install.install_claude_code(tmp_path, dry_run=False)
    assert len(installed) == len(install.list_skills())
    for dest in installed:
        assert (Path(dest) / "SKILL.md").exists()
    marker = tmp_path / install.MARKER
    record = json.loads(marker.read_text(encoding="utf-8"))
    assert "claude-code" in record["hosts"]
    assert len(record["hosts"]["claude-code"]["files"]) == len(installed)


def test_marker_merges_hosts(tmp_path: Path):
    """审查意见#2 回归：同一目标根安装两个宿主，清单互不覆盖。"""
    install.install_claude_code(tmp_path, dry_run=False)
    install.install_generic(tmp_path, dry_run=False)
    record = json.loads((tmp_path / install.MARKER).read_text(encoding="utf-8"))
    assert set(record["hosts"]) == {"claude-code", "generic"}


def test_unmanaged_dir_backed_up(tmp_path: Path):
    """审查意见#1 回归：不受管的同名目录被备份而非删除。"""
    dest = tmp_path / ".codex" / "plugins" / "study-copilot"
    dest.mkdir(parents=True)
    (dest / "user-custom.txt").write_text("用户自有内容", encoding="utf-8")
    install.install_codex(tmp_path, dry_run=False)
    assert (dest / ".codex-plugin" / "plugin.json").exists()  # 新安装成功
    bak = dest.with_name("study-copilot.bak")
    assert (bak / "user-custom.txt").exists()  # 旧内容被备份


def test_corpus_survives_broken_queue(tmp_path):
    """审查意见#3 回归：错题队列损坏不阻塞 md 语料采集。"""
    import sys as _sys
    _sys.path.insert(0, str(REPO / "scripts"))
    from local_retrieval import corpus as corpus_mod
    qdir = tmp_path / "30-知识"
    qdir.mkdir(parents=True)
    (qdir / "错题队列.json").write_text("{ 不是合法JSON", encoding="utf-8")
    (qdir / "笔记.md").write_text("# 笔记", encoding="utf-8")
    docs = corpus_mod.collect(tmp_path)
    assert any(d["doc_id"].startswith("md:") for d in docs)


def test_install_codex(tmp_path: Path):
    install.install_codex(tmp_path, dry_run=False)
    dest = tmp_path / ".codex" / "plugins" / "study-copilot"
    assert (dest / ".codex-plugin" / "plugin.json").exists()
    assert (dest / "skills" / "kaoyan-error-loop-coach" / "SKILL.md").exists()


def test_install_generic(tmp_path: Path):
    install.install_generic(tmp_path, dry_run=False)
    doc = tmp_path / "AGENTS-STUDY-COPILOT.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "kaoyan-subject-onboarding" in text


def test_uninstall_cleans(tmp_path: Path):
    install.install_claude_code(tmp_path, dry_run=False)
    assert install.uninstall(tmp_path, dry_run=False) == 0
    assert not (tmp_path / ".claude" / "skills" / "kaoyan-error-loop-coach").exists()
    assert not (tmp_path / install.MARKER).exists()


def test_dry_run_no_writes(tmp_path: Path):
    install.install_claude_code(tmp_path, dry_run=True)
    assert not (tmp_path / ".claude").exists()
    assert not (tmp_path / install.MARKER).exists()


def test_detect_host(monkeypatch, tmp_path):
    monkeypatch.setattr(install.Path, "home", staticmethod(lambda: tmp_path))
    assert install.detect_host() == "generic"
    (tmp_path / ".claude").mkdir()
    assert install.detect_host() == "claude-code"
    (tmp_path / ".codex").mkdir()
    assert install.detect_host() == "codex"
