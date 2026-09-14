# 学习副驾 Study Copilot

> 装进任何 AI Agent 的通用学习认知引擎 —— 任何宿主 Agent × 任何科目，预置考研包。

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) [![CI](https://github.com/yq6666-66/study-copilot-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/yq6666-66/study-copilot-skills/actions/workflows/ci.yml) [English](docs/README.en.md)

**学习副驾**是一套纯 Skills 的学习认知引擎：不依赖任何后台服务，把它装进你的 AI Agent（Codex、Claude Code 等），Agent 就拥有跨会话的学习记忆、错题闭环、间隔复测、学习规划、进度诊断与原创模考能力。

前身是 [408考研插件](https://github.com/yq6666-66/408-codex-plugin)（kaoyan-408 v2.4.0）。本项目的核心升级是把学习机制从「考研专用」泛化为两层通用：

1. **任何 Agent** —— Skills 核心与宿主解耦，通过适配层安装到不同 AI Agent。
2. **任何科目** —— 学习机制层天然科目无关（错题、规划、诊断、模考的数据 Schema 中科目就是自由字段）；学科内容由「科目配置包」驱动，预置考研包，新科目可由向导生成。

## 功能总览

### 错题闭环

- **错因聚类**：跨题聚类错因，严格区分「已确认」与「假设」两种状态；假设错因在复测通过前不参与掌握判定。
- **间隔复测排期**：内置 [FSRS](https://github.com/open-spaced-repetition/fsrs4anki) 调度（遗忘曲线 / 初始稳定性 / 均值回归阻尼），按你的历史评分动态计算每条错题的建议复习日与今日可提取概率。
- **掌握证据判定**：复测通过不算掌握——延迟一段时间后再次复测仍通过，才升级为「已掌握」并移出活跃队列。
- 边界：不凭空推断错因；用户未给出的部分一律标记为假设并要求确认。

### 规划与执行

- **目标倒排**：按考试目标日期倒排阶段 / 月度 / 周度计划，自动处理跨科配额与冲突。
- **时间盒展开**：把「本周要完成什么」展开为立即可做的时间盒任务，做完即记录。
- 边界：计划基于既有记录与用户输入生成，不虚构进度。

### 进度诊断与原创模考

- **进度诊断**：只基于真实学习记录（错题、复测、计划完成度）输出偏差、风险与调整信号。
- **原创模考**：组织冻结题面的原创模考，交卷前不讲题、不提示；阅卷后回流错题闭环。
- 边界：题面缺失或答案冲突时明确报告，不猜测补全。

### 学科辅导与真题工作流

- 四科学科辅导（408 / 数学 / 英语 / 政治）：概念讲解、单题讲评（可要求「只指第一处错误」）、专项训练。
- **真题两件套**：真题来源搜索与许可核验（无授权不抓取）、对已核验样本的分析；重复来源自动去重。
- **材料学习**：把你自己的讲义 / 笔记转成摘要、卡片、提纲或原创练习。
- **官方信息核验**：核验当年招考信息与录取数据，标注来源与时效。

### 端侧语义检索（本地 AI PC，数据不出域）

本地 CPU 运行 embedding 模型（bge-small-zh-v1.5，ONNX）为错题队列与笔记建立语义索引，毫秒级召回相似历史错题；向量缓存 + 增量索引让 2000 条规模改 1% 数据的重索引从 7.3s 降到 0.39s（19×）。模型不可用时自动退化为关键词匹配，功能不中断。

```bash
# 建索引（首次自动下载模型；--fake 可离线冒烟）
python scripts/local_retrieval/embed_index.py

# 语义检索相似错题 / 笔记
python scripts/local_retrieval/semantic_search.py --query "进程死锁检测和银行家算法又算错了" --top-k 5

# 增量更新（只重编码变更部分）
python scripts/local_retrieval/embed_index.py --incremental
```

### 云端变式陪练（可选 · 任意 OpenAI 兼容模型服务）

配置好云端模型环境变量后，Agent 可调用云端大模型做**定向变式出题与二次精讲**：基于已确认的错因生成变式题（不复制原题面），并支持一键把新科目（法考 / CPA / 任意科目）接入为配置包。**未配置时全部功能照常离线可用**，仅云端专项降级并明示，不伪造生成结果。

```bash
# 一键端云协同演示：端侧召回相似错题 → 云端生成变式题（--dry-cloud 只预览 prompt）
python scripts/demo_pipeline.py --item r028

# 考前预练：端侧召回 → 定向变式卷 → Markdown 输出（--no-qwen 离线模式）
python scripts/pre_drill.py --index demo-vault/30-知识/.index --topic 进程死锁 银行家算法 --qwen
```

### 学习工具链

```bash
python scripts/study_report.py --queue demo-vault/30-知识/错题队列.json          # 学习周报（掌握概览/错题热点/FSRS 负载）
python scripts/export_anki.py --queue demo-vault/30-知识/错题队列.json --out anki.csv   # 导出 Anki 卡片（含 FSRS 字段）
python scripts/study_dashboard.py --queue demo-vault/30-知识/错题队列.json --out dash.html  # 静态 HTML 仪表盘（遗忘曲线 SVG）
```

## 数据与记忆

学习数据全部落在用户本地，格式可携带：

| 内容 | 落点 |
| --- | --- |
| 错题队列 | `demo-vault/30-知识/错题队列.json`（ReviewQueue Schema 1.1，字段含错因状态 / FSRS 稳定性难度 / 复测历史） |
| 端侧向量索引 | `<语料>/30-知识/.index/`（向量 + npz 缓存，纯本地文件） |
| 学习记忆 | 用户自己的 Obsidian Vault（`00-系统 / 20-项目 / 30-知识 / 40-真题` 四目录约定） |
| 科目配置 | `subjects/<科目>/profile.json`（考研预置；新科目由向导生成同构配置） |

不接 Vault 也能用：错题队列就是一个 JSON 文件，放在哪里、叫什么由你决定。

## 使用方法

### 在哪里使用

- **Codex / Codex CLI**：`python install.py --host codex`，装进 `~/.codex/` 插件目录。
- **Claude Code**：`python install.py --host claude-code`，装进 `~/.claude/skills/`。
- **其他 Agent**：任意能读 Markdown Skill 文件的 Agent，用 `--host generic --target <目录>` 安装到指定位置后按该 Agent 的方式加载。

### 记忆控制

- 不接 Vault：学习记录只存在错题队列 JSON，删掉即清空，无任何隐藏状态。
- 接 Vault：笔记与复盘写入你指定的 Vault 目录，路径在科目配置中声明；安装器与 Skill 只写入这些目录，**绝不触碰其他路径**。
- 卸载：`--uninstall` 按安装清单精确清理，学习数据目录不在清理范围。

### 常用问法

装好后直接对 Agent 说（以下均可直接复制）：

| 场景 | 示例问法 |
| --- | --- |
| 录入错题 | 「把这道题记入错题队列，我的错因是……，状态先记为假设」 |
| 错因聚类与复测 | 「整理 408-操作系统的错题，把错因相近的聚成簇，按 FSRS 安排复测」 |
| 今日复习清单 | 「今天该复测哪些错题？给出清单和每条的可提取概率」 |
| 生成计划 | 「目标 12 月 21 日初试，倒排未来 8 周计划并展开为本周时间盒」 |
| 讲题 | 「讲这道题，只指出我的第一处错误，先别给答案」 |
| 变式陪练 | 「针对错题 r028 的已确认错因出一道变式题考我，答完再讲评」 |
| 考前预练 | 「明天考操作系统，就“进程死锁与银行家算法”出一份考前预练卷」 |
| 原创模考 | 「组织一次 408 模考，冻结题面，交卷前不讲题」 |
| 进度诊断 | 「诊断我最近两周的进度偏差和风险，给出调整建议」 |
| 语义检索 | 「和我之前哪道错题最像：“页缺失中断处理流程”？」 |
| 周报 / Anki | 「生成本周学习周报」「把当前错题队列导出成 Anki 卡片」 |
| 新科目接入 | 「我要备考法考，生成法考科目配置包」（走 `kaoyan-subject-onboarding` 向导） |

## 架构

详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

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

# 1. 预览将安装的内容（不写入任何文件）
python install.py --list
python install.py --host auto --dry-run

# 2. 安装到你的 Agent（auto 自动探测 Codex / Claude Code）
python install.py --host claude-code     # Codex 用户: --host codex

# 3. 校验数据资产（Schema 1.1 + 科目配置）
python scripts/validate_records.py

# 4. 对 Agent 说第一句话：「今天该复测哪些错题？」
```

云端变式陪练为可选功能，接入任意 OpenAI 兼容的模型服务（OpenAI、DeepSeek、Kimi、硅基流动、本地 Ollama / vLLM 等均可）。密钥只存你机器的环境变量，本仓库不保存任何凭据：

1. **拿到三项信息**：在你选择的模型服务商控制台获取兼容端点（Base URL）、模型名和 API Key。
2. **配置三个环境变量**：

   ```powershell
   # Windows（PowerShell）——配置后需重开终端生效
   setx OPENAI_BASE_URL "<服务商兼容端点，如 https://api.deepseek.com/v1>"
   setx OPENAI_MODEL "<模型名>"
   setx OPENAI_API_KEY "<你的API Key>"
   ```

   ```bash
   # macOS / Linux（写入 ~/.zshrc 或 ~/.bashrc 可永久生效）
   export OPENAI_BASE_URL="<服务商兼容端点>"
   export OPENAI_MODEL="<模型名>"
   export OPENAI_API_KEY="<你的API Key>"
   ```

3. **验证**：`python scripts/demo_pipeline.py --item r028` 跑通端侧召回 → 云端变式题全链路（先离线预览可加 `--dry-cloud`）。

不配置则所有功能保持离线可用。

## 15 个主责 Skill

| Skill | 主责 | 示例触发 |
| --- | --- | --- |
| `kaoyan-408-planner` | 阶段、月度、周度、目标日期倒排和跨科配额 | 「倒排未来 8 周计划」 |
| `kaoyan-review-executor` | 把既有计划或本次目标展开为立即可做的时间盒 | 「展开为本周时间盒」 |
| `kaoyan-progress-diagnostician` | 根据记录诊断偏差、风险和调整信号 | 「诊断最近两周进度」 |
| `kaoyan-error-loop-coach` | 跨题聚类错因、复测和掌握证据 | 「整理错题并安排复测」 |
| `kaoyan-mock-exam-coach` | 组织原创或用户授权的冻结题面模考 | 「组织一次模考」 |
| `kaoyan-408-tutor` | 408 概念、单题、题面缺失和答案冲突 | 「讲这道题」 |
| `kaoyan-math-coach` | 数学一/二概念、单题、第一处错误和专项训练 | 「只指第一处错误」 |
| `kaoyan-english-coach` | 英语一/二阅读、翻译、完形、新题型和写作 | 「批改这篇作文」 |
| `kaoyan-politics-coach` | 政治理论、材料题、作答批改和背诵复测 | 「这题怎么答」 |
| `kaoyan-past-paper-searcher` | 发现、核验、许可判断、去重和登记真题来源 | 「找历年真题」 |
| `kaoyan-past-paper-analyst` | 分析已提供或已核验可访问的真题样本 | 「分析这套真题」 |
| `kaoyan-material-study-assistant` | 把用户材料转成摘要、卡片、提纲或原创练习 | 「把讲义做成卡片」 |
| `kaoyan-official-info-researcher` | 核验当年招考信息与录取数据 | 「查今年招生简章」 |
| `kaoyan-qwen-drill` | 云端大模型错题陪练（任意 OpenAI 兼容服务）：变式复测出题与二次精讲 | 「针对 r028 出变式题」 |
| `kaoyan-subject-onboarding` | 新科目接入向导：生成科目配置包并验证机制层零改动 | 「我要备考法考」 |

> 学科命名中的「考研/408」是历史沿革；机制层科目无关，泛化改造按科目配置层推进。

## 推荐串联

- `官方核验 → 规划 → 执行`
- `真题搜索 → 真题分析 → 学科辅导`
- `学科辅导 → 错题闭环 → 进度诊断`
- `模考 → 错题闭环 → 进度诊断`

## 隐私

学习记录、错题、笔记只存用户本地（Obsidian Vault / 本地 JSON）。见 [PRIVACY.md](PRIVACY.md)。

## 许可

[MIT](LICENSE) © yq6666-66
