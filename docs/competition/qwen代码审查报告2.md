---
generator: Qwen (qwen-flash)
log: logs/qwen/20260913-232638-qwen-flash.json
---

# 代码审查报告 2：qwen_engine.py 自审（Qwen 生成）

> [Qwen生成] 由云端 Qwen（qwen-flash）真实生成，调用留痕：`logs/qwen/20260913-232638-qwen-flash.json`（1525 tokens）。

1. **问题**：`latency_ms =` 语句不完整，缺少赋值表达式，导致语法错误。  
   **影响**：代码无法运行，抛出 `SyntaxError`。  
   **最小修复建议**：补全为 `latency_ms = int((time.time() - started) * 1000)`。

2. **问题**：`_get_api_key()` 函数未被调用，实际只使用 `os.environ.get("DASHSCOPE_API_KEY")` 和 `_registry_key()`，逻辑冗余且存在潜在误用风险。  
   **影响**：函数无实际作用，增加维护负担；若后续修改逻辑可能引入错误。  
   **最小修复建议**：删除未使用的 `_get_api_key()` 函数。

3. **问题**：`call_qwen` 函数中未对 `resp.json()` 进行异常处理，当响应非 JSON 格式时会抛出 `json.JSONDecodeError`。  
   **影响**：网络异常或服务返回非标准格式时程序崩溃。  
   **最小修复建议**：在 `resp.json()` 前添加 `resp.raise_for_status()` 并捕获异常，确保容错。
