# 科目配置层

学习机制层（错题闭环、规划、诊断、模考）天然科目无关：数据 Schema（ReviewQueue / StudyProfile / ProgressSnapshot）中 `subject` 是自由字符串。学科内容则由**科目配置包**驱动——每个包是一个 `profile.json`，声明该科目族下的科目、负责的学科 coach Skill 与大纲主题。

## 目录

```
subjects/
├── kaoyan/profile.json    # 考研预置包（数学一/二、英语一/二、408、政治）
├── TEMPLATE/profile.json  # 新科目包模板
└── README.md              # 本文件
```

## profile.json 结构

```json
{
  "package": "kaoyan",
  "displayName": "考研",
  "subjects": [
    {
      "id": "math-1",
      "name": "数学一",
      "coachSkill": "kaoyan-math-coach",
      "syllabusTopics": ["高等数学-函数极限连续", "..."],
      "examMeta": { "schedule": "每年12月下旬" }
    }
  ]
}
```

| 字段 | 说明 |
| --- | --- |
| `package` | 包标识（英文，即目录名） |
| `subjects[].id` | 科目标识，写入错题队列 `subject` 字段时用 `name`（中文），`id` 供程序过滤 |
| `subjects[].coachSkill` | 学科讲解的主责 Skill；通用机制 Skill（规划/诊断/闭环）不需要映射 |
| `subjects[].syllabusTopics` | 大纲主题清单，供规划切分与错题聚类对齐 |
| `subjects[].examMeta` | 考试元信息（时间、满分、卷种差异等），只记录用户提供的官方事实 |

## 新增科目包（法考 / CPA / 高考 / 期末考…）

1. `cp -r subjects/TEMPLATE subjects/<package-id>/`
2. 准备材料：该科目的大纲/教材目录、目标日期、可用的学科讲解方式。
3. 让 Agent 使用 `kaoyan-subject-onboarding` 向导生成并校验 `profile.json`。
4. 验证：用新科目 id 写一条错题进 ReviewQueue → 错题闭环照常聚类 → 规划器照常排期。机制层无需任何代码改动。

> 学科 coach 若现有 Skill 不匹配（如法考主观题讲法），向导会建议新建一个薄 coach Skill 或先复用 `kaoyan-material-study-assistant`（材料转练习）兜底。
