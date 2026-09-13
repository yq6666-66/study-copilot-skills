---
name: kaoyan-qwen-drill
description: 基于错题簇调用云端 Qwen（DashScope）生成变式复测题与二次精讲。用户说“用Qwen陪练”“针对这个错题簇出变式题”“这题再讲一遍”时使用；单题首次讲解归学科教练，不替代端侧语义检索与错因聚类。
---

# Qwen 错题陪练

## 加载契约

- 始终读取并遵循[能力路由契约](../../references/capability-routing-contract.md)。
- 调用前必须读取 [Qwen 云端引擎契约](../../references/qwen-engine-contract.md)。
- 输入是错题簇时，先确认已有 `kaoyan-error-loop-coach` 的交接卡或用户直接提供的错题记录。
- 生成复测题时遵循[证据与版权契约](../../references/evidence-copyright-contract.md)。

## 陪练流程

1. 接收错题簇（科目、知识点、错因、confirmed/hypothesis 状态）；缺错因描述时只请求最小补充。
2. 将错因与知识点组织成 prompt，写明约束：**只输出原创变式题，不复制任何原题题面**；围绕已确认错因设陷阱，围绕假设错因做最小验证。
3. 先以 `python scripts/qwen_engine.py --dry-run` 预览请求体，确认不含个人信息后真实调用；默认 `qwen-flash`。
4. 产出格式：
   - 变式复测题标 `[原创练习][Qwen生成]`，作答前不附答案或提示。
   - 二次精讲标 `[Qwen生成]`，并对照用户原错因逐条回应。
   - 附本次调用日志路径（`logs/qwen/…json`）作为 AI 实践佐证。
5. 云端失败或未配置 Key 时降级：会话内出题，明示「本次未使用 Qwen」，不伪造 `[Qwen生成]` 标注。

## 边界

- 不做单题首次讲解（归学科教练）；不改写 `ReviewQueue` 状态——掌握判定仍由错题闭环的证据规则决定。
- 一次请求聚焦一个错题簇；不做整卷生成，不绕过版权约束。
