---
generator: Qwen (qwen3.8-flash)
log: logs/qwen/20260913-234708-qwen3.8-flash.json
---

# 代码审查报告 3：install.py 与 corpus.py（qwen3.8-flash）

> [Qwen生成]（qwen3.8-flash）真实生成，留痕：`logs/qwen/20260913-234708-qwen3.8-flash.json`（4960 tokens）。

模块A-安装 codex/claude 前对 `dest` 直接 `shutil.rmtree`，未校验目录是否由本安装器管理-可能误删用户已有的 `.codex/plugins/study-copilot` 或 `.claude/skills/<skill>` 自定义内容-仅当 marker 记录或明确属于本插件时清理，否则备份或拒绝覆盖。

模块A-`_write_marker` 每次覆盖 `target_root/.study-copilot-installed.json`-同一目标根安装多个宿主或重复安装不同宿主时，旧清单丢失，`--uninstall` 无法完整清理-按 host 分文件写清单，或合并保留各 host 的安装记录。

模块B-`collect` 直接 `json.loads(queue.read_text(...))` 且假定 `data` 为 dict-错题队列为空文件、非法 JSON 或顶层不是对象时抛异常，导致整个语料采集失败-读取 JSON 包 `try/except`，并校验 `isinstance(data, dict)` 后再取 `items`。

模块B-`doc_id` 使用 `item.get("id", i)`-当 `id` 为 `null`/空字符串或重复时，可能生成 `review:None`、`review:` 或重复 `doc_id`，破坏索引/去重-改为 `item.get("id") or i`，并在生成时确保 `doc_id` 唯一。
