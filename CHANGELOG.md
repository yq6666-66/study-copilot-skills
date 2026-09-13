# 更新日志

本项目所有条目的依据：git 提交历史（公开）、`logs/qwen/` 调用留痕（25 份）、GitHub Actions 运行记录（run ID 公开可查）、`docs/competition/Qwen会话优化实录.md`（逐轮明细）。

## v1.9 — 2026-09-14（第十四轮：Anki 导出）

### 新增
- `scripts/export_anki.py`：错题队列 → Anki 可导入 CSV（UTF-8 BOM；Front/Back/Tags/Stability/Difficulty/IntervalDays/SuggestedNextDate/Status 八列；`--only-active`、`--delimiter` 选项）。
- `--qwen-prompts` 模式：卡片措辞由 qwen-flash 改写为回忆式（提示词硬约束 Front 禁含答案；第 28 次留痕 `20260914-035446`，5,154 tokens）；示例 `docs/competition/anki导出示例.csv`。
- 安全：Mimosa 路径穿越告警驱动结构重构——核心函数只处理文本、文件 I/O 收敛到 main() 内联守卫（禁 `..` 段 + 限定仓库目录）；7 个回归测试。

### 变更
- 材料计数 28 次 / 75,378 tokens / ×22+×6。78 tests。

## v1.8 — 2026-09-14（第十三轮：功能扩展）

### 新增
- `scripts/scheduler.py`：FSRS 间隔复习调度器（遗忘曲线/初始稳定性/均值回归阻尼/期望保持率反解间隔；公式逐行对照 open-spaced-repetition/fsrs-rs 源码；错题队列集成含 bootstrap 显式标记），8 测试。
- `scripts/study_report.py`：学习周报生成器（掌握概览/错题热点/7 天 FSRS 负载/可选 Qwen 洞察段），3 测试；示例 `docs/competition/学习周报示例.md`（洞察段第 27 次留痕 `20260914-034212`）。
- 数字门禁实战：新留痕后捕获 9 处文档计数漂移并全量修复（27 次 / 70,224 tokens / ×21+×6）。71 tests。

## v1.7 — 2026-09-14（第十二轮：数字一致性门禁）

### 新增
- 第六道 CI 门禁 `scripts/check_numbers.py`：四份材料的调用数/模型分布/token 累计/表行数必须等于 `logs/qwen/` 真值；本地双模式互查仓库内脱敏 `docs/competition/留痕索引.json`（无内容，仅文件名/模型/用量/时延），CI 索引模式实弹通过（run `34777570473`）。+4 测试共 60。

## v1.6 — 2026-09-14（第十一轮：国际化）

### 新增
- `docs/README.en.md` 英文版：初稿由云端 qwen-flash 生成（留痕 `20260914-030050`，7,330 tokens），人工审校修正 4 处过时数字（15 Skill/23 契约/26 次调用/最新 run ID）并删内部里程碑术语；中文 README 顶部加 English 链接、Skill 表补至 15 行。CI 矩阵 run `34776615998` 全绿。

## v1.5 — 2026-09-14（第九轮：契约覆盖度门禁）

### 新增
- `scripts/check_contract_coverage.py` 入 CI：度量并断言 15 个 Skill × 23 份契约的引用矩阵——**零死链、零孤儿契约**（100% 可达，含契约间路由引用）；4 个回归测试（漂移与孤岛场景必报红），run `34775399129` 三版本矩阵全绿。

## v1.4 — 2026-09-14（第七轮：兼容性实证）

### 变更
- CI 升级为 Python **3.10 / 3.11 / 3.12 版本矩阵**（fail-fast off；semgrep 仅 3.12 执行）——52 tests × 3 版本全绿（run `34774366234`、`34774683664`）。

## v1.3 — 2026-09-14（第五~六轮：文档质量与错误体验）

### 新增
- `docs/ARCHITECTURE.md`：初稿由云端 qwen3.8-flash 生成（留痕 `20260914-014216`，14,173 tokens），人工审校删除 1 处虚构历史叙述、机器核验 42 个回引用路径。
- `scripts/check_doc_paths.py`：文档路径引用门禁入 CI（AI 生成文档的路径漂移防线；首跑由 CI 抓出自身 `.index` 环境假设 bug 并修复，run `34773001227`）。
- CLI 错误消息可操作化：401 双平台 Key 指引、429 具体降级命令、模型未就绪实测大小与下一步动作；7 个回归测试。
- `scripts/qwen_engine.py` 新增 `--stats`：一键聚合全部留痕（25 次 / 62,413 tokens / Key 泄漏 0）。
- 错误文案经 qwen3.8-flash 评审采纳 3 条建议，评审 prompt 中埋入的事实错误（100MB→54.6MB）被正确抓出（留痕 `20260914-020602`）。

## v1.2 — 2026-09-14（第三~四轮：演示管道、性能基准与安全门禁）

### 新增
- `scripts/demo_pipeline.py`：一键端云协同演示（端侧召回 0.03s → Qwen 8.9s 出题 → 留痕，锚点演示调用留痕 `20260914-005709`）；跨模型维度错配自动重建。
- `scripts/bench.py` + `docs/competition/端侧性能基准.md`：2000 条实测——增量更新 0.39s vs 全量 7.31s（19×）、查询 p95 28.8ms；基准过程抓出并修复两处自身问题（JSON 缓存负优化→npz 二进制；测量方法未预填缓存）。
- `.semgrep.yml` 安全门禁入 CI（7 规则；首跑抓出文档 2 处用户绝对路径泄露，脱敏清零）。
- 规划师与模考教练接入端侧语义检索契约（契约引用 3→5：弱项加权规划、组卷考点覆盖）。

## v1.1 — 2026-09-13 深夜 ~ 09-14（第一~二轮：内容链路与工程底座）

### 新增
- Qwen 专项链路扩展至 **16 次真实调用**（数学/408 变式题、法考与注会科目配置包入库 `subjects/fakao/`、`subjects/cpa/`、原创练习集×3、错因聚类报告、代码审查×3、双模型对比、复测计划、FAQ、README 实录专节）。
- GitHub Actions CI 从零建立（移植丢失补齐；首跑抓出 `winreg` 与 `skipif` 两个 Windows 本机不可见的跨平台 bug 并修复转绿，run `34769398038`）。
- `scripts/validate_records.py` 数据资产校验器；真增量索引 `--incremental`；真实模型检索质量端到端测试（CI 自动 skip）；索引二进制清理出库。
- 端侧向量缓存 `scripts/local_retrieval/vec_cache.py`（59 篇重建 2.2s→0.0s）。

## v1.0 — 2026-09-13（奠基）

### 新增
- 项目自前作 408 考研插件 v2.4.0 泛化重建：15 个 Skills（13 移植 + qwen-drill + subject-onboarding）、23 份契约与 Schema、多宿主安装器（Codex / Claude Code / 通用）、科目配置层、端侧 bge-small-zh 语义检索、Qwen DashScope 引擎（留痕+防泄漏+401 注册表候选）、脱敏演示库（40 条错题 × 2 科目，Schema 校验）、参赛文档三件套与程序化演示视频（神经网络配音 + 烧录字幕）。
- 首批 Qwen 真实调用 6 次（陪练/配置/聚类/FAQ，留痕 `20260913-211223` 起）。

### 安全
- 凭据仅从环境变量或 Windows 用户级注册表读取；仓库、示例与测试不含任何凭据字面量；semgrep 门禁持续把关。
