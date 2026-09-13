# -*- coding: utf-8 -*-
"""数据资产校验器：演示 Vault、科目配置等 JSON 的结构与 Schema 校验。

用法（仓库根目录）：
    python scripts/validate_records.py
退出码 0 = 全部通过；非 0 = 有问题并逐条列出。CI 与本地共用同一入口。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:  # pragma: no cover
    print("缺少 jsonschema：pip install jsonschema")
    raise SystemExit(2)

REPO = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO / "plugins/study-copilot/references/portable-learning-records.schema.json"
BLOCK_RE = re.compile(r"```json\n(.*?)```", re.S)


def _check_json_block(schema, text: str, source: str, errors: list) -> int:
    checked = 0
    for i, block in enumerate(BLOCK_RE.findall(text)):
        checked += 1
        try:
            jsonschema.validate(json.loads(block), schema)
        except (json.JSONDecodeError, jsonschema.ValidationError) as exc:
            errors.append("{}[块{}]: {}".format(source, i, str(exc)[:160]))
    return checked


def validate_records(errors: list) -> int:
    """返回校验通过的记录份数。"""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    n = 0
    queue = REPO / "demo-vault/30-知识/错题队列.json"
    if queue.exists():
        jsonschema.validate(json.loads(queue.read_text(encoding="utf-8")), schema)
        n += 1
    else:
        errors.append("缺少 {}".format(queue.relative_to(REPO)))
    for md in sorted(REPO.glob("demo-vault/20-项目/*.md")):
        n += _check_json_block(schema, md.read_text(encoding="utf-8"), md.name, errors)
    return n


def validate_profiles(errors: list) -> int:
    """校验 subjects/*/profile.json 结构。返回份数。"""
    n = 0
    for p in sorted((REPO / "subjects").glob("*/profile.json")):
        n += 1
        try:
            cfg = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append("{}: JSON 解析失败 {}".format(p.relative_to(REPO), exc))
            continue
        for field in ("package", "displayName", "subjects"):
            if field not in cfg:
                errors.append("{}: 缺字段 {}".format(p.relative_to(REPO), field))
        subjects = cfg.get("subjects")
        if not isinstance(subjects, list) or not subjects:
            errors.append("{}: subjects 必须为非空数组".format(p.relative_to(REPO)))
            continue
        for s in subjects:
            missing = [f for f in ("id", "name", "coachSkill", "syllabusTopics") if not s.get(f)]
            if missing:
                errors.append("{}: 科目 {} 缺 {}".format(p.relative_to(REPO), s.get("id", "?"), missing))
    return n


def main() -> int:
    errors: list = []
    records = validate_records(errors)
    profiles = validate_profiles(errors)
    if errors:
        print("校验失败 {} 项：".format(len(errors)))
        for e in errors:
            print("  -", e)
        return 1
    print("OK：学习记录 {} 份 + 科目配置 {} 份全部通过校验".format(records, profiles))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
