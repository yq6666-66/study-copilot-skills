# -*- coding: utf-8 -*-
"""参赛作品包组装脚本。

按比赛要求生成三层结构并打包 ZIP：
    学习副驾_<参赛者名>.zip
    ├── 作品展示文件夹/      项目源码 + 演示视频占位
    ├── AI实践验证文件夹/    Qwen留痕 / 端侧检索证据 / 关键代码 / Prompt设计 / 测试记录
    └── 体验说明.md

用法（仓库根目录下运行）：
    python assemble_package.py --name 参赛者名
录完演示视频后把 mp4/GIF 放入 作品展示文件夹/演示视频/ 再重跑一次即可。
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import sys
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent
DIST = REPO / "dist"
EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", "models", "dist", ".index", "logs", ".codex"}
EXCLUDE_FILES = {".gitignore", "assemble_package.py"}
sys.path.insert(0, str(REPO / "scripts"))


def _capture(main_fn, argv: list[str]) -> str:
    """进程内调用 CLI 的 main()，捕获 stdout。"""
    buf = io.StringIO()
    old_argv = sys.argv
    try:
        sys.argv = argv
        with contextlib.redirect_stdout(buf):
            try:
                main_fn()
            except SystemExit as exc:  # argparse/CLI 常规退出
                if exc.code not in (0, None):
                    buf.write("\n[exit code: {}]".format(exc.code))
    finally:
        sys.argv = old_argv
    return buf.getvalue()


def copy_source(dst: Path) -> int:
    count = 0
    for src in REPO.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(REPO)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if src.name in EXCLUDE_FILES or src.suffix in {".pyc", ".log"}:
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        count += 1
    return count


def build_evidence(ev: Path) -> None:
    # 01 Qwen 留痕
    qdir = ev / "01-Qwen调用留痕"
    qdir.mkdir(parents=True)
    logs = sorted((REPO / "logs" / "qwen").glob("*.json"))
    for f in logs:
        shutil.copy2(f, qdir / f.name)
    if logs:
        record = json.loads(logs[-1].read_text(encoding="utf-8"))
        messages = record.get("messages") or []
        note = (
            "# Qwen 真实调用说明\n\n"
            "- 接口：DashScope OpenAI 兼容模式（`scripts/qwen_engine.py`）\n"
            "- 模型：{model}；finish_reason：{finish}\n"
            "- token 用量：{usage}；时延：{lat}ms\n"
            "- 留痕文件与原始请求/响应完全一致，不含 API Key（引擎内置防泄漏断言，见测试）\n\n"
            "## 实际 Prompt（system）\n\n```\n{sys}\n```\n\n"
            "## 实际 Prompt（user）\n\n```\n{user}\n```\n\n"
            "## Qwen 返回（节选前 800 字）\n\n```\n{resp}\n```\n"
        ).format(
            model=record.get("model"), finish=record.get("finish_reason"),
            usage=record.get("usage", {}).get("total_tokens"), lat=record.get("latency_ms"),
            sys=messages[0].get("content", "") if messages else "",
            user=messages[-1].get("content", "") if len(messages) > 1 else "",
            resp=(record.get("response_content") or "")[:800],
        )
        (qdir / "调用说明.md").write_text(note, encoding="utf-8")

    # 02 端侧检索证据（真实模型进程内跑）
    from local_retrieval import embed_index, semantic_search
    rdir = ev / "02-端侧检索证据"
    rdir.mkdir(parents=True)
    (rdir / "建索引输出.txt").write_text(
        _capture(embed_index.main, ["embed_index.py"]), encoding="utf-8")
    for label, query in (("检索-操作系统-死锁.json", "进程死锁检测和银行家算法又算错了"),
                         ("检索-数学-级数.json", "级数收敛判别方法总是选错")):
        out = _capture(semantic_search.main,
                       ["semantic_search.py", "--query", query, "--top-k", "5"])
        (rdir / label).write_text(out, encoding="utf-8")

    # 03 关键代码
    cdir = ev / "03-关键代码"
    cdir.mkdir(parents=True)
    shutil.copy2(REPO / "scripts" / "qwen_engine.py", cdir / "qwen_engine.py")
    lr = cdir / "local_retrieval"
    lr.mkdir(exist_ok=True)
    for f in (REPO / "scripts" / "local_retrieval").glob("*.py"):
        shutil.copy2(f, lr / f.name)

    # 04 Prompt 与 Skill 设计
    pdir = ev / "04-Prompt与Skill设计"
    pdir.mkdir(parents=True)
    shutil.copy2(REPO / "plugins/study-copilot/skills/kaoyan-qwen-drill/SKILL.md", pdir / "kaoyan-qwen-drill-SKILL.md")
    for name in ("qwen-engine-contract.md", "local-semantic-retrieval-contract.md"):
        shutil.copy2(REPO / "plugins/study-copilot/references" / name, pdir / name)

    # 05 测试记录（进程内 pytest）
    import pytest
    tdir = ev / "05-测试记录"
    tdir.mkdir(parents=True)
    (tdir / "pytest输出.txt").write_text(
        _capture(pytest.main, ["pytest", "tests/", "-q"]), encoding="utf-8")

    # 06 DashScope 控制台用量佐证（平台侧官方记录，与 logs/qwen 交叉核验）
    console_src = REPO / "docs" / "competition" / "控制台用量"
    if console_src.exists():
        cdir = ev / "06-DashScope控制台用量"
        cdir.mkdir(parents=True)
        for img in sorted(console_src.glob("*.png")):
            shutil.copy2(img, cdir / img.name)
        (cdir / "说明.md").write_text(
            "# 控制台用量佐证说明\n\n"
            "本目录两张截图来自千问AI平台（DashScope）「用量分析→按量付费」官方页面（2026-09-14）：\n"
            "- 01-用量总览.png：近 1 周 390 请求 / 226.9M tokens / 成功率 100.0%；模型分项 "
            "qwen3.8-max 282 次、qwen3.8-flash 281 次（平均延迟 26.9s）、qwen-flash 27 次，均 100% 成功。\n"
            "- 02-调用日志.png：逐条 Request ID / 模型 / token 明细（共 392 条，含输入/输出/图片 token 与时延）。\n\n"
            "**口径区分（重要）**：本作品包代码链路产生的调用为 36 次（`logs/qwen/` 逐一留痕，"
            "qwen-flash ×30 + qwen3.8-flash ×6），是上述控制台总量的真子集；"
            "其余为开发过程中以 Qwen 模型作为编程会话引擎产生的用量（qwen3.8-max 等）。"
            "两类用途在《AI技术实践说明》中分别披露，不混用、不夸大。\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="组装参赛作品包")
    parser.add_argument("--name", default="参赛者名", help="参赛者姓名（用于 ZIP 文件名）")
    args = parser.parse_args()

    started = time.time()
    pkg = DIST / "学习副驾_{}".format(args.name)
    if pkg.exists():
        shutil.rmtree(pkg)
    show = pkg / "作品展示文件夹"
    ev = pkg / "AI实践验证文件夹"
    show.mkdir(parents=True)
    ev.mkdir(parents=True)

    n_files = copy_source(show / "项目源码")
    # 技术栈全景图放展示文件夹根层，评委解压第一眼可见
    stack_img = REPO / "docs" / "competition" / "技术栈图.png"
    if stack_img.exists():
        shutil.copy2(stack_img, show / "技术栈图.png")
    vdir = show / "演示视频"
    vdir.mkdir()
    # 自动收集已生成的演示资产（scripts/make_video.py 的产物）
    video = REPO / "dist" / "学习副驾演示视频.mp4"
    if video.exists():
        shutil.copy2(video, vdir / "学习副驾演示视频.mp4")
        for g in (REPO / "dist" / "video_work").glob("gif*.gif"):
            shutil.copy2(g, vdir / g.name)
    else:
        (vdir / "说明.txt").write_text(
            "生成演示视频：python scripts/make_video.py（约 1 分钟，需联网配音）。\n"
            "录制实拍版参考 项目源码/docs/competition/演示视频录制操作手册.md。\n", encoding="utf-8")

    build_evidence(ev)
    shutil.copy2(REPO / "docs/competition/体验说明.md", pkg / "体验说明.md")
    overview = REPO / "docs/competition/千问证据总览.md"
    if overview.exists():
        shutil.copy2(overview, pkg / "千问证据总览.md")  # ZIP 根层：解压第一眼

    zip_path = DIST / "学习副驾_{}.zip".format(args.name)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(pkg.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(pkg))  # 顶层直接是三个条目，符合比赛规范

    size_mb = zip_path.stat().st_size / 1048576
    print("作品包完成：{}".format(zip_path))
    print("  源码文件 {} 个；总大小 {:.1f} MB；耗时 {:.1f}s".format(n_files, size_mb, time.time() - started))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
