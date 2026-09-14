# -*- coding: utf-8 -*-
"""云端模型引擎（OpenAI 兼容接口，服务商无关）。

学习副驾的云端推理通道：默认承担「错题陪练」链路（变式复测出题与二次精讲）。
任意 OpenAI 兼容的模型服务均可接入（OpenAI / DeepSeek / Kimi / 硅基流动 / 本地 Ollama 等），
通过三个环境变量配置；每次真实调用写留痕日志到 logs/qwen/。

用法（仓库根目录下运行）：
    python scripts/qwen_engine.py --system "..." --prompt "..."
    python scripts/qwen_engine.py --messages-file msg.json --model deepseek-chat
    python scripts/qwen_engine.py --dry-run --prompt "预览请求"

配置（按优先级）：
    OPENAI_BASE_URL  服务商兼容端点（如 https://api.openai.com/v1，自动拼 /chat/completions）
    OPENAI_MODEL     模型名（或 LLM_MODEL）
    OPENAI_API_KEY   密钥（或 LLM_API_KEY / DASHSCOPE_API_KEY，向后兼容）
Key 只从环境变量读取，绝不写入日志。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List

import requests

DEFAULT_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DEFAULT_MODEL = "qwen-flash"
KEY_ENV_VARS = ("OPENAI_API_KEY", "LLM_API_KEY", "DASHSCOPE_API_KEY")
REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = REPO_ROOT / "logs" / "qwen"


def endpoint() -> str:
    """兼容端点：OPENAI_BASE_URL 优先（自动拼 /chat/completions），否则用默认端点。"""
    base = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
    if base:
        return base + "/chat/completions"
    return DEFAULT_ENDPOINT


def default_model() -> str:
    return os.environ.get("OPENAI_MODEL", "") or os.environ.get("LLM_MODEL", "") or DEFAULT_MODEL


def build_messages(system: str | None, prompt: str | None, messages_file: str | None) -> List[dict]:
    if messages_file:
        data = json.loads(Path(messages_file).read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(m, dict) for m in data):
            raise ValueError("messages-file 必须是 JSON 数组（[{role, content}, ...]）")
        return data
    if not prompt:
        raise ValueError("必须提供 --prompt 或 --messages-file")
    messages: List[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


def _assert_no_secret(text: str) -> None:
    for key in _key_candidates():
        if key in text:
            raise AssertionError("安全断言失败：输出内容包含 API Key，拒绝写入日志")


def _registry_key() -> str | None:
    """Windows 用户级注册表中的最新 Key（setx 立即写这里，进程环境变量则滞后）；非 Windows 返回 None。"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            for var in KEY_ENV_VARS:
                try:
                    val, _ = winreg.QueryValueEx(k, var)
                    if val:
                        return val or None
                except OSError:
                    continue
            return None
    except (ImportError, OSError):
        return None


def _key_candidates() -> List[str]:
    """Key 候选链：OPENAI_API_KEY → LLM_API_KEY → DASHSCOPE_API_KEY（环境变量）→ Windows 注册表。"""
    keys: List[str] = []
    for var in KEY_ENV_VARS:
        v = os.environ.get(var)
        if v and v not in keys:
            keys.append(v)
    reg = _registry_key()
    if reg and reg not in keys:
        keys.append(reg)
    return keys


def call_qwen(messages: List[dict], model: str | None = None, temperature: float = 0.7,
              max_tokens: int | None = None, timeout: int = 60, log: bool = True) -> dict:
    """调用一次 chat/completions，返回含日志路径的结果字典。

    model 为 None 时取 default_model()（OPENAI_MODEL / LLM_MODEL / 内置默认）。
    Key 候选：进程环境变量（OPENAI_API_KEY 优先）→ Windows 注册表（防 setx 后进程滞后）。
    401 invalid_api_key 且还有下一个候选时自动切换重试。
    """
    model = model or default_model()
    keys = _key_candidates()
    if not keys:
        raise RuntimeError(
            "未配置云端模型密钥。请设置环境变量 OPENAI_API_KEY（兼容 LLM_API_KEY / DASHSCOPE_API_KEY），"
            "Windows 执行 setx OPENAI_API_KEY \"<你的Key>\" 后新开终端。"
            "无 Key 时请使用降级路径（会话内出题），不阻塞学习。"
        )

    payload = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens:
        payload["max_tokens"] = max_tokens

    started = time.time()
    resp = None
    for ki, api_key in enumerate(keys):
        for attempt in (1, 2):
            resp = requests.post(
                endpoint(),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload, timeout=timeout,
            )
            if resp.status_code == 429 and attempt == 1:
                time.sleep(2 ** attempt)
                continue
            if resp.status_code >= 500 and attempt == 1:
                time.sleep(2)
                continue
            break
        if resp.status_code == 401 and ki + 1 < len(keys):
            continue  # 进程环境变量可能滞后于最新 setx，换注册表候选重试
        break
    latency_ms = int((time.time() - started) * 1000)

    if resp.status_code != 200:
        raise RuntimeError("云端调用失败 HTTP {}: {}{}".format(
            resp.status_code, resp.text[:300], _http_action_hint(resp.status_code)))

    body = resp.json()
    choice = (body.get("choices") or [{}])[0]
    content = choice.get("message", {}).get("content", "")
    usage = body.get("usage", {}) or {}
    finish_reason = choice.get("finish_reason")

    log_path = None
    if log:
        _assert_no_secret(json.dumps(messages, ensure_ascii=False))
        _assert_no_secret(content)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        log_path = LOG_DIR / "{}-{}.json".format(stamp, model.replace("/", "-"))
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "model": model,
            "messages": messages,
            "response_content": content,
            "usage": usage,
            "latency_ms": latency_ms,
            "finish_reason": finish_reason,
        }
        log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"content": content, "usage": usage, "latency_ms": latency_ms,
            "finish_reason": finish_reason, "model": model, "log_path": str(log_path) if log_path else None}


def stats(log_dir: Path = LOG_DIR) -> dict:
    """聚合全部调用留痕：按模型统计次数/token/时延分布与 finish_reason；复核日志不含 Key。"""
    if not log_dir.exists():
        return {"calls": 0, "note": "无留痕目录", "by_model": {}}
    api_keys = [k for k in _key_candidates() if k]
    total = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    by_model: dict = {}
    latencies: list = []
    key_leak = 0
    for f in sorted(log_dir.glob("*.json")):
        try:
            record = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        m = record.get("model") or "unknown"
        usage = record.get("usage") or {}
        slot = by_model.setdefault(m, {"calls": 0, "total_tokens": 0})
        slot["calls"] += 1
        slot["total_tokens"] += usage.get("total_tokens") or 0
        total["calls"] += 1
        total["prompt_tokens"] += usage.get("prompt_tokens") or 0
        total["completion_tokens"] += usage.get("completion_tokens") or 0
        total["total_tokens"] += usage.get("total_tokens") or 0
        if record.get("finish_reason"):
            fr = by_model[m].setdefault("finish_reasons", {})
            fr[record["finish_reason"]] = fr.get(record["finish_reason"], 0) + 1
        if record.get("latency_ms"):
            latencies.append(record["latency_ms"])
        if api_keys and any(k in f.read_text(encoding="utf-8") for k in api_keys):
            key_leak += 1
    out = dict(total)
    out["by_model"] = by_model
    if latencies:
        out["latency_ms"] = {"min": min(latencies), "max": max(latencies),
                             "avg": round(sum(latencies) / len(latencies))}
    out["api_key_leaked_logs"] = key_leak
    return out


def _http_action_hint(status: int) -> str:
    """面向使用者的可操作指引。"""
    if status in (401, 403):
        return (" → Key 可能失效或未开通：请到你的模型服务商控制台重建 Key；Windows 执行 setx OPENAI_API_KEY \"<你的Key>\""
                "并**新开终端**，macOS/Linux 执行 export OPENAI_API_KEY=\"<你的Key>\" 后重试；"
                "若仍失败，请确认对应模型已开通。")
    if status == 429:
        return (" → 触发限流/额度：可改用低成本模型重试（配置 OPENAI_MODEL 或调用时传 --model）；"
                "继续使用原模型请稍后重试，或走会话内降级。")
    if status >= 500:
        return " → 服务端异常：稍后重试；持续失败请查看你的模型服务商状态页。"
    return " → 原始请求与错误已打印；调用可通过 --dry-run 先行自检。"


def main() -> int:
    parser = argparse.ArgumentParser(description="云端模型引擎（OpenAI 兼容接口，任意服务商，调用全留痕）")
    parser.add_argument("--model", default=None, help="模型名（默认取 OPENAI_MODEL/LLM_MODEL 或内置默认）")
    parser.add_argument("--system", default=None, help="system 提示词")
    parser.add_argument("--prompt", default=None, help="user 提示词")
    parser.add_argument("--messages-file", default=None, help="JSON 文件：完整 messages 数组")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="只打印将发送的请求体，不联网")
    parser.add_argument("--no-log", action="store_true", help="本次调用不留痕")
    parser.add_argument("--json", action="store_true", help="输出完整 JSON（含日志路径）")
    parser.add_argument("--stats", action="store_true",
                        help="聚合 logs/qwen/ 全部留痕的统计（不发请求）")
    args = parser.parse_args()

    if args.stats:
        print(json.dumps(stats(), ensure_ascii=False, indent=2))
        return 0

    try:
        messages = build_messages(args.system, args.prompt, args.messages_file)
    except (ValueError, OSError) as exc:
        print("参数错误：{}".format(exc))
        return 2

    if args.dry_run:
        preview = {"model": args.model or default_model(), "temperature": args.temperature,
                   "max_tokens": args.max_tokens, "messages": messages,
                   "endpoint": endpoint(), "log_path_planned": str(LOG_DIR)}
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    try:
        result = call_qwen(messages, model=args.model, temperature=args.temperature,
                           max_tokens=args.max_tokens, log=not args.no_log)
    except RuntimeError as exc:
        print("调用失败：{}".format(exc))
        return 2
    except requests.RequestException as exc:
        print("网络异常：{}".format(exc))
        return 3

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["content"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
