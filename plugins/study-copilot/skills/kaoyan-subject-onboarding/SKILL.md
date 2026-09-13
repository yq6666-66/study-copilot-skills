---
name: kaoyan-subject-onboarding
description: 为任何科目生成科目配置包（subjects/<package>/profile.json），让学习副驾支持法考、CPA、高考、期末考等非考研科目。用户说“我要加法考”“帮我配置CPA科目”“让插件支持高考数学”时使用；不编造官方考试信息，不替代学科讲解。
---

# 科目接入向导

## 加载契约

- 生成配置前读取 [能力路由契约](../../references/capability-routing-contract.md) 与 [便携学习记录契约](../../references/portable-learning-records.md)。
- 配置结构以仓库 `subjects/README.md` 与 `subjects/TEMPLATE/profile.json` 为准。

## 接入流程

1. 确认目标：包名（英文标识，即目录名）、显示名、目标考试日期、科目清单。
2. 索取最小材料：该科目的大纲或教材目录（用户提供的标 `[用户材料]`）；缺大纲时可让用户口述章节清单，**不凭记忆编造考纲**。
3. 每个科目确定：
   - `id`（英文）与 `name`（中文，将写入错题队列 `subject` 字段）；
   - `coachSkill` 映射：有现成学科 Skill 则映射之；没有则默认 `kaoyan-material-study-assistant`（材料转练习兜底），并在说明中建议后续补建薄 coach；
   - `syllabusTopics`：来自用户材料，逐条可核对；
   - `examMeta`：只记录用户提供的官方事实。
4. 生成 `subjects/<package>/profile.json`，输出接入清单：文件路径、科目数、下一步验证步骤。
5. 验证演示：用新科目 `name` 写一条示例错题进 ReviewQueue，确认错题闭环、规划、端侧检索均按普通字符串科目正常工作（机制层无需改代码）。

## 边界

- 不获取未提供的材料；大纲信息必须可追溯到 `[用户材料]` 或官方页面核验（交 `kaoyan-official-info-researcher`）。
- 不在本流程中做学科讲解；不修改已有科目包。
