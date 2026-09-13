# -*- coding: utf-8 -*-
"""Skill 契约引用覆盖度分析与死链门禁。

度量 skills/ 下 15 个 SKILL.md 与 references/ 契约之间的引用关系：
1. 【断言】所有被引用的契约目标必须真实存在（相对链接死链 = 契约漂移，CI 失败）；
2. 【报告】每份契约的可达性：被任一 Skill 或任一契约（能力路由等）引用为可达，
   否则列为孤儿并失败——新增契约必须接进路由或 Skill，防止文档孤岛。

用法（仓库根目录）：
    python scripts/check_contract_coverage.py            # 表格 + 判定
    python scripts/check_contract_coverage.py --json     # 机器可读
退出码 0 = 无死链且无孤儿；1 = 有违规。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO / "plugins/study-copilot" / "skills"
REF_DIR = REPO / "plugins/study-copilot" / "references"
LINK = re.compile(r"\]\(([^)]+?\.(?:md|json))\)")


def collect(skills_dir: Path = SKILLS_DIR, ref_dir: Path = REF_DIR) -> dict:
    skills = {}
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        refs = set()
        for target in LINK.findall(skill_md.read_text(encoding="utf-8", errors="ignore")):
            if "references/" in target:
                refs.add(target.split("references/")[-1])
        skills[skill_md.parent.name] = refs
    contracts = sorted(p.name for p in ref_dir.iterdir() if p.suffix in (".md", ".json"))
    # 契约间引用（能力路由等按需加载声明）
    ref_usage = set()
    for doc in ref_dir.glob("*.md"):
        for target in LINK.findall(doc.read_text(encoding="utf-8", errors="ignore")):
            ref_usage.add(Path(target).name)
    dead = []
    for skill, refs in skills.items():
        for r in sorted(refs):
            if not (ref_dir / r).exists():
                dead.append("{} -> {}".format(skill, r))
    orphans = [c for c in contracts if c not in ref_usage and not any(c in refs for refs in skills.values())]
    covered = {c for refs in skills.values() for c in refs if (ref_dir / c).exists()} | (ref_usage & set(contracts))
    return {
        "skills": len(skills), "contracts": len(contracts),
        "skill_refs": {k: sorted(v) for k, v in skills.items()},
        "covered": len(covered), "dead_links": dead, "orphans": orphans,
    }


def main() -> int:
    argv = sys.argv[1:]
    report = collect()
    if "--json" in argv:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Skill {} 个 × 契约 {} 份；被引用覆盖 {} 份".format(
            report["skills"], report["contracts"], report["covered"]))
        for skill, refs in report["skill_refs"].items():
            if refs:
                print("  {} → {}".format(skill, "、".join(refs)))
    ok = not report["dead_links"] and not report["orphans"]
    if report["dead_links"]:
        print("死链 {} 处：".format(len(report["dead_links"])))
        for d in report["dead_links"]:
            print("  -", d)
    if report["orphans"]:
        print("孤儿契约 {} 份：".format(len(report["orphans"])))
        for o in report["orphans"]:
            print("  -", o)
    print("结果：{}".format("OK——无死链、无孤儿契约" if ok else "不通过"))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
