# Qwen 会话优化实录（会话级痕迹）

> 与 `logs/qwen/` 里的 **API 调用级**留痕互补：本文件记录的是
> **qwen3.8-flash 作为 ZCode 编程会话的驱动模型，直接对本项目实施的深度优化**。
> 即：下面的代码不是人类手写的，也不是 GLM 写的——由 Qwen 模型在本次结对编程会话中完成。

## 会话身份与证据

| 项 | 值 |
| --- | --- |
| 会话 ID | `sess_2bb5c0e4-3f82-42d0-b232-f7e34b9ae539` |
| 驱动模型 | `qwen3.8-flash`（provider: `qwen-alibaba-model-studio-cn`） |
| 证据来源 | ZCode 模型 I/O 日志 `~/.zcode/cli/rollout/model-io-sess_2bb5c0e4-….jsonl`，每轮请求/响应含 `model.modelId` 字段 |
| 优化时间 | 2026-09-14 00:08–00:15（北京时间） |
| 代码落地 | git commit（消息标注「Qwen 会话驱动」），GitHub 公开可查 |

**核验方式（如实说明）**：这是**本机可验**的证据——评委现场打开 ZCode 任一会话的设置/日志即可看到模型字段；git 历史时间线与本实录对得上。它与 DashScope 控制台的公开用量证据互补，不互相冒充。

## 本次会话完成的优化（qwen3.8-flash 驱动）

### A. 端侧检索·向量缓存（性能优化）

- 新增 `scripts/local_retrieval/vec_cache.py`：按 `模型名+sha256(文本)` 缓存 embedding 结果至索引目录 `emb_cache.json`；重建索引只对新增/变更文本重新计算。
- 设计要点：换模型不污染缓存（键含模型名）、重复文本只算一次、缓存损坏静默作废、`--no-cache` 可关。
- **真实测（59 篇文档，真实 bge 模型）**：首次建索引 2.2s → 二次重建 **0.0s**（59 全命中，零重算）——增量更新场景下重复计算成本降为零。

### B. Qwen 引擎·留痕聚合统计（可审计性优化）

- `scripts/qwen_engine.py` 新增 `--stats`：一行命令聚合 `logs/qwen/` 全部留痕。
- 真实输出（生成于 2026-09-14）：**22 次调用 / 44,220 tokens（prompt 8,172 + completion 36,048）/ qwen-flash ×18、qwen3.8-flash ×4 / 时延 min 2,160ms avg 16,049ms max 83,686ms / finish_reason 全部 stop / API Key 泄漏数 0**。
- 损坏日志文件自动跳过；复核逻辑内置「日志不含 Key」扫描。

### 质量保障

- 新增 8 个离线回归测试（缓存 6 + stats 2），全套 **29 passed**。

## 口径边界

- 本次是「Qwen 模型驱动的开发会话」；此前会话中本项目的部分基础设施代码由 GLM 辅助完成（两者在 PRIVACY.md 与 AI 技术实践说明中分别如实披露）。
- 项目运行时链路（错题陪练/配置生成等 22 次调用）仍为 DashScope API 级留痕，见《千问证据总览.md》。
