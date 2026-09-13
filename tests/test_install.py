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
    assert record["host"] == "claude-code"
    assert len(record["files"]) == len(installed)


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
