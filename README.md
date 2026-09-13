# 学习副驾 Study Copilot

> 装进任何 AI Agent 的通用学习认知引擎 —— 任何宿主 Agent × 任何科目，预置考研包。

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**学习副驾**是一套纯 Skills 的学习认知引擎：不依赖任何后台服务，把它装进你的 AI Agent（Codex、Claude Code 等），Agent 就拥有跨会话的学习记忆、错题闭环、间隔复测、学习规划、进度诊断与原创模考能力。

> 仓库：https://github.com/yq6666-66/study-copilot-skills ｜ 前作（408考研插件 v2.4.0）：https://github.com/yq6666-66/408-codex-plugin

前身是 [408考研插件](https://github.com/yq6666-66/408-codex-plugin)（kaoyan-408 v2.4.0）。本项目的核心升级是把学习机制从「考研专用」泛化为两层通用：

1. **任何 Agent** —— Skills 核心与宿主解耦，通过适配层安装到不同 AI Agent。
2. **任何科目** —— 学习机制层天然科目无关（错题、规划、诊断、模考的数据 Schema 中科目就是自由字段）；学科内容由「科目配置包」驱动，预置考研包，新科目可由向导生成。

## 特性

- 🔁 **错题闭环**：跨题聚类错因（区分已确认与假设）、间隔复测排期、延迟掌握证据判定
- 📅 **规划与执行**：按目标日期倒排的阶段/月度/周度计划，展开为立即可做的时间盒
- 📊 **进度诊断**：基于记录的诊断，不凭空生成进度
- 📝 **原创模考**：冻结题面组织模考，交卷前不讲题
- 🧠 **本地学习记忆**：可选接入用户自己的 Obsidian Vault，跨会话记忆只存本地
- 🔍 **端侧语义检索**（新增）：本地 CPU 运行 embedding 模型，为错题队列/真题索引做语义检索，与云端大模型协同
- 📦 **科目配置驱动**（新增）：`subjects/` 预置考研包；法考、CPA、高考等新科目由 `subject-onboarding` 向导接入

## 架构

```
┌─────────────────────────────────────────────────┐
│  宿主适配层 adapters/                             │
│  Codex(.codex-plugin) · Claude Code · 文档级适配  │
├─────────────────────────────────────────────────┤
│  通用 Skills 核心 plugins/study-copilot/skills/  │
│  错题闭环 · 规划 · 执行 · 诊断 · 模考 · 真题契约   │
│  （科目无关的学习机制层）                          │
├─────────────────────────────────────────────────┤
│  科目配置层 subjects/                             │
│  考研预置包（数一/数二/英一/英二/408/政治）+ 向导   │
├─────────────────────────────────────────────────┤
│  数据与记忆层（全部在用户本地）                     │
│  ReviewQueue · StudyProfile · Obsidian Vault     │
│  端侧 embedding 索引（bge-small-zh，CPU）         │
└─────────────────────────────────────────────────┘
```

## 快速开始

```bash
git clone https://github.com/yq6666-66/study-copilot-skills.git
cd study-copilot-skills

# 任一宿主（自动探测 Codex / Claude Code；--dry-run 先预览）
python install.py --host auto --dry-run
python install.py --host claude-code     # 装到 ~/.claude/skills/（Codex 用户: --host codex）

# 5 分钟体验路径见 docs/competition/体验说明.md
```

## 目录结构

```
study-copilot-skills/
├── plugins/study-copilot/     # Skills 核心（13 个主责 Skill + 21 个契约）
│   ├── skills/
│   ├── references/            # 行为契约与数据 Schema
│   ├── assets/
│   └── .codex-plugin/plugin.json
├── adapters/                  # 宿主适配层
├── subjects/                  # 科目配置包（考研预置 + 向导）
├── scripts/local_retrieval/   # 端侧语义检索（embedding 索引/查询）
├── demo-vault/                # 脱敏演示 Vault
├── docs/competition/          # 参赛文档（AI 技术实践说明等）
└── tests/                     # pytest 测试
```

## 13 个主责 Skill

| Skill | 主责意图 |
| --- | --- |
| `kaoyan-408-planner` | 阶段、月度、周度、目标日期倒排和跨科配额 |
| `kaoyan-review-executor` | 把既有计划或本次目标展开为立即可做的时间盒 |
| `kaoyan-progress-diagnostician` | 根据记录诊断偏差、风险和调整信号 |
| `kaoyan-error-loop-coach` | 跨题聚类错因、复测和掌握证据 |
| `kaoyan-mock-exam-coach` | 组织原创或用户授权的冻结题面模考 |
| `kaoyan-408-tutor` | 408 概念、单题、题面缺失和答案冲突 |
| `kaoyan-math-coach` | 数学一/二概念、单题、第一处错误和专项训练 |
| `kaoyan-english-coach` | 英语一/二阅读、翻译、完形、新题型和写作 |
| `kaoyan-politics-coach` | 政治理论、材料题、作答批改和背诵复测 |
| `kaoyan-past-paper-searcher` | 发现、核验、许可判断、去重和登记真题来源 |
| `kaoyan-past-paper-analyst` | 分析已提供或已核验可访问的真题样本 |
| `kaoyan-material-study-assistant` | 把用户材料转成摘要、卡片、提纲或原创练习 |
| `kaoyan-official-info-researcher` | 核验当年招考信息与录取数据 |

> 学科命名中的「考研/408」是历史沿革；机制层科目无关，泛化改造按科目配置层推进（见 M1 里程碑）。

## 推荐串联

- `官方核验 → 规划 → 执行`
- `真题搜索 → 真题分析 → 学科辅导`
- `学科辅导 → 错题闭环 → 进度诊断`
- `模考 → 错题闭环 → 进度诊断`

## 隐私

学习记录、错题、笔记只存用户本地（Obsidian Vault / 本地 JSON）。见 [PRIVACY.md](PRIVACY.md)。

## 许可

[MIT](LICENSE) © yq6666-66
