# 宿主适配层

学习副驾的 Skills 核心与宿主解耦：`plugins/study-copilot/skills/` 下的每个 `SKILL.md` 都带标准 frontmatter（`name` / `description`），可被多种 AI Agent 直接加载。本目录存放各宿主的适配说明与差异记录。

## 宿主矩阵

| 宿主 | 适配方式 | 安装命令 | 状态 |
| --- | --- | --- | --- |
| Codex | 原生插件：`plugins/study-copilot/`（含 `.codex-plugin/plugin.json`）复制到 `~/.codex/plugins/study-copilot/` | `python install.py --host codex` | 实测可用 |
| Claude Code | Skills 直拷：每个 Skill 目录复制到 `~/.claude/skills/<name>/` | `python install.py --host claude-code` | 实测可用（见 [claude-code/README.md](claude-code/README.md)） |
| Cursor | 文档级：将 SKILL.md 作为 Rules 引用 | 参考 `AGENTS-STUDY-COPILOT.md` 片段 | 文档级 |
| 通用 Agent | 文档级：生成接入说明，手动纳入上下文 | `python install.py --host generic` | 文档级 |

智能探测：`python install.py --host auto` 按 `~/.codex` → `~/.claude` 顺序探测，都没有则 generic。

## 数据路径的发现顺序

Obsidian 大脑等本地记忆契约原先硬编码 `~/.codex/kaoyan-408/`。跨宿主后统一按以下顺序解析配置目录：

1. 环境变量 `STUDY_COPILOT_HOME`（最高优先）
2. `~/.study-copilot/`
3. 旧版 `~/.codex/kaoyan-408/`（向后兼容，已有用户数据不动）

## 卸载

安装器在目标根写入 `.study-copilot-installed.json` 清单，卸载按清单清理：

```bash
python install.py --host claude-code --uninstall
```

安装器绝不触碰学习数据目录（Vault、配置目录、`logs/`）。
