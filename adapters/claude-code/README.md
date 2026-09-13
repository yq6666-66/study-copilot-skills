# Claude Code 适配

## 为什么可以直接装

Claude Code 的 Skill 约定与本项目 SKILL.md 的 frontmatter 一致：目录名即 Skill 名，`SKILL.md` 首部为 `name` / `description` YAML。因此安装就是把 `plugins/study-copilot/skills/<name>/` 复制到 `~/.claude/skills/<name>/`，无格式转换。

## 安装

```bash
python install.py --host claude-code          # 正式安装
python install.py --host claude-code --dry-run  # 先预览
```

## 差异与限制

| 项 | Codex 原生 | Claude Code 适配 |
| --- | --- | --- |
| 插件元数据（plugin.json） | 读取 | 不读取（仅展示层差异，不影响 Skill 行为） |
| Skill 发现 | `.codex-plugin` 声明的 `skills/` | `~/.claude/skills/` 目录约定 |
| 契约文件引用 | Skill 内相对路径 `../../references/` | 安装的是单 Skill 目录，契约需一并可达 |

**契约可达性处理**：部分契约（如 `capability-routing-contract.md`）被多个 Skill 引用。Claude Code 下两种做法：

1. 推荐：额外把整个 `plugins/study-copilot/` 克隆到本地任意固定路径，在 `CLAUDE.md` 中写明「契约根目录 = 该路径」，Skill 内的契约链接按该路径解析。
2. 简化：让 Claude Code 会话的工作目录就是本仓库根目录，相对路径天然成立。

## 本地记忆配置路径

按 [adapters/README.md](../README.md) 的发现顺序：`STUDY_COPILOT_HOME` → `~/.study-copilot/` → 旧版 `~/.codex/kaoyan-408/`。首次使用可从模板生成配置（参考 obsidian-brain-contract.md 的 Schema 1.1）。
