# -*- coding: utf-8 -*-
"""契约覆盖度门禁回归测试：真实仓库必须全绿；构造漂移场景必须报红。"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from check_contract_coverage import collect  # noqa: E402


def test_real_repo_has_no_dead_links_and_no_orphans():
    r = collect()
    assert r["skills"] == 15
    assert r["contracts"] == 23
    assert r["dead_links"] == []
    assert r["orphans"] == []
    assert r["covered"] == r["contracts"]


def test_dead_link_detected(tmp_path):
    skills, refs = tmp_path / "skills", tmp_path / "references"
    (skills / "a").mkdir(parents=True)
    (refs).mkdir()
    (refs / "real.md").write_text("# 契约", encoding="utf-8")
    (skills / "a" / "SKILL.md").write_text(
        "见 [契约](../../references/real.md) 与 [幽灵](../../references/ghost.md)", encoding="utf-8")
    r = collect(skills, refs)
    assert r["dead_links"] == ["a -> ghost.md"]


def test_orphan_contract_detected(tmp_path):
    skills, refs = tmp_path / "skills", tmp_path / "references"
    (skills / "a").mkdir(parents=True)
    refs.mkdir()
    (refs / "used.md").write_text("# used", encoding="utf-8")
    (refs / "stranded.md").write_text(
        "本契约不被任何 Skill 或契约引用（路由正文也没提）", encoding="utf-8")
    (skills / "a" / "SKILL.md").write_text("[契约](../../references/used.md)", encoding="utf-8")
    r = collect(skills, refs)
    assert r["orphans"] == ["stranded.md"]


def test_contract_to_contract_reference_counts_as_reachable(tmp_path):
    skills, refs = tmp_path / "skills", tmp_path / "references"
    (skills / "a").mkdir(parents=True)
    refs.mkdir()
    (skills / "a" / "SKILL.md").write_text("[路由](../../references/routing.md)", encoding="utf-8")
    (refs / "routing.md").write_text("提供工具时读取 [子契约](sub-contract.md)。", encoding="utf-8")
    (refs / "sub-contract.md").write_text("# 子契约", encoding="utf-8")
    r = collect(skills, refs)
    assert r["dead_links"] == [] and r["orphans"] == []
