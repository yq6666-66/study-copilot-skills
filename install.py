# -*- coding: utf-8 -*-
"""学习副驾安装器：把 Skills 装进不同宿主 Agent。

用法（仓库根目录下运行）：
    python install.py --list
    python install.py --host auto --dry-run
    python install.py --host claude-code
    python install.py --host codex
    python install.py --host codex --target <目录> --dry-run
    python install.py --host claude-code --uninstall

安装产物在目标根写入 .study-copilot-installed.json（清单），--uninstall 按清单清理，
绝不触碰学习数据目录（Vault、~/.codex/kaoyan-408/ 等）。
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
PLUGIN_DIR = REPO_ROOT / "plugins" / "study-copilot"
SKILLS_DIR = PLUGIN_DIR / "skills"
MARKER = ".study-copilot-installed.json"


def list_skills() -> list[str]:
    return sorted(p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").exists())


def _read_marker(target_root: Path) -> dict:
    p = target_root / MARKER
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"hosts": {}}


def _write_marker(target_root: Path, files: list[str], host: str) -> None:
    """按宿主合并安装清单（qwen3.8-flash 审查意见#2）：同一目标根装多个宿主互不覆盖。"""
    record = _read_marker(target_root)
    record.setdefault("hosts", {})[host] = {"installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                            "files": files}
    (target_root / MARKER).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def _managed_by_us(dest: Path, target_root: Path, host: str) -> bool:
    """dest 是否在本安装器的清单里（qwen3.8-flash 审查意见#1）：不受管的目录不直接删除。"""
    record = _read_marker(target_root)
    for f in record.get("hosts", {}).get(host, {}).get("files", []):
        if Path(f) == dest or dest in Path(f).parents or Path(f) in dest.parents:
            return True
    return False


def _safe_replace_dir(dest: Path, target_root: Path, host: str) -> None:
    """覆盖安装前保护：不受管目录先备份为 .bak 而非直接删除。"""
    if dest.exists() and not _managed_by_us(dest, target_root, host):
        bak = dest.with_name(dest.name + ".bak")
        if bak.exists():
            shutil.rmtree(bak)
        dest.rename(bak)
        print("已将非本安装器管理的目录备份为：{}".format(bak))
    elif dest.exists():
        shutil.rmtree(dest)


def _plan_summary(action: str, items: list[str]) -> None:
    print("[{}]".format(action))
    for item in items:
        print("  -", item)
    print("共 {} 项。".format(len(items)))


def install_codex(target_root: Path, dry_run: bool) -> list[str]:
    dest = target_root / ".codex" / "plugins" / "study-copilot"
    plan = ["复制 {} → {}".format(PLUGIN_DIR, dest)]
    if dry_run:
        _plan_summary("DRY-RUN codex", plan)
        return [str(dest)]
    _safe_replace_dir(dest, target_root, "codex")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PLUGIN_DIR, dest)
    _write_marker(target_root, [str(dest)], "codex")
    print("已安装（Codex）：{}".format(dest))
    return [str(dest)]


def install_claude_code(target_root: Path, dry_run: bool) -> list[str]:
    dest_root = target_root / ".claude" / "skills"
    installed: list[str] = []
    for skill in list_skills():
        src = SKILLS_DIR / skill
        dest = dest_root / skill
        plan = ["复制 {} → {}".format(src, dest)]
        if dry_run:
            _plan_summary("DRY-RUN claude-code", plan)
            installed.append(str(dest))
            continue
        _safe_replace_dir(dest, target_root, "claude-code")
        shutil.copytree(src, dest)
        installed.append(str(dest))
    if dry_run:
        return installed
    _write_marker(target_root, installed, "claude-code")
    print("已安装（Claude Code）：{} 个 Skill → {}".format(len(installed), dest_root))
    return installed


def install_generic(target_root: Path, dry_run: bool) -> list[str]:
    dest = target_root / "AGENTS-STUDY-COPILOT.md"
    content = (
        "# 学习副驾 Study Copilot（通用接入）\n\n"
        "把本仓库 plugins/study-copilot/skills/ 下各 SKILL.md 纳入你的 Agent 上下文：\n\n"
        "- 兼容 frontmatter（name/description）的 Agent：整目录复制即可被发现。\n"
        "- 其他 Agent：将各 SKILL.md 内容作为系统指令/规则注入，按 capability-routing-contract.md 路由。\n\n"
        "Skill 清单（{} 个）：\n{}\n\n契约目录：plugins/study-copilot/references/\n".format(
            len(list_skills()), "\n".join("- " + s for s in list_skills()))
    )
    plan = ["写入 {}".format(dest)]
    if dry_run:
        _plan_summary("DRY-RUN generic", plan)
        return [str(dest)]
    target_root.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    _write_marker(target_root, [str(dest)], "generic")
    print("已写入通用接入说明：{}".format(dest))
    return [str(dest)]


def detect_host() -> str:
    home = Path.home()
    if (home / ".codex").exists():
        return "codex"
    if (home / ".claude").exists():
        return "claude-code"
    return "generic"


def uninstall(target_root: Path, dry_run: bool) -> int:
    marker = target_root / MARKER
    if not marker.exists():
        print("未找到安装清单 {}，无法安全卸载。".format(marker))
        return 1
    record = _read_marker(target_root)
    hosts = record.get("hosts", {})
    all_files = [f for entries in hosts.values() for f in entries.get("files", [])]
    if dry_run:
        _plan_summary("DRY-RUN uninstall", all_files)
        return 0
    for item in all_files:
        p = Path(item)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    marker.unlink()
    print("已卸载 {} 项（hosts={}）。".format(len(all_files), ", ".join(hosts) or "无"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="学习副驾安装器")
    parser.add_argument("--host", choices=["auto", "codex", "claude-code", "generic"], default="auto")
    parser.add_argument("--target", default=None, help="目标根目录（默认用户主目录）")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--list", action="store_true", help="列出可安装的 Skill")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.list:
        for skill in list_skills():
            print(skill)
        return 0

    target_root = Path(args.target).expanduser() if args.target else Path.home()
    if args.uninstall:
        return uninstall(target_root, args.dry_run)

    host = detect_host() if args.host == "auto" else args.host
    if not args.dry_run and args.target is None:
        print("目标：{}（host={}）。正式安装到用户主目录前，建议先加 --dry-run 预览。".format(target_root, host))
    if args.host == "codex":
        install_codex(target_root, args.dry_run)
    elif args.host == "claude-code":
        install_claude_code(target_root, args.dry_run)
    elif args.host == "generic":
        install_generic(target_root, args.dry_run)
    else:
        install_codex(target_root, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
