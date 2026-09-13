# -*- coding: utf-8 -*-
"""云端 Qwen 引擎（DashScope OpenAI 兼容接口）。

学习副驾的云端推理通道：默认承担「错题陪练」链路（变式复测出题与二次精讲）。
每次真实调用写留痕日志到 logs/qwen/，作为 AI 实践佐证。

用法（仓库根目录下运行）：
    python scripts/qwen_engine.py --system "..." --prompt "..."
    python scripts/qwen_engine.py --messages-file msg.json --model qwen-plus
    python scripts/qwen_engine.py --dry-run --prompt "预览请求"

鉴权：环境变量 DASHSCOPE_API_KEY（Windows 配置：setx DASHSCOPE_API_KEY "sk-..."）。
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

ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DEFAULT_MODEL = "qwen-flash"
REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = REPO_ROOT / "logs" / "qwen"


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
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if key and key in text:
        raise AssertionError("安全断言失败：输出内容包含 API Key，拒绝写入日志")


def call_qwen(messages: List[dict], model: str = DEFAULT_MODEL, temperature: float = 0.7,
              max_tokens: int | None = None, timeout: int = 60, log: bool = True) -> dict:
    """调用一次 chat/completions，返回含日志路径的结果字典。"""
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "未配置 DASHSCOPE_API_KEY。Windows 配置：setx DASHSCOPE_API_KEY \"sk-你的Key\"，"
            "然后新开终端生效。无 Key 时请使用降级路径（会话内出题），不阻塞学习。"
        )

    payload = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens:
        payload["max_tokens"] = max_tokens

    started = time.time()
    for attempt in (1, 2):
        resp = requests.post(
            ENDPOINT,
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
    latency_ms = int((time.time() - started) * 1000)

    if resp.status_code != 200:
        raise RuntimeError("Qwen 调用失败 HTTP {}: {}".format(resp.status_code, resp.text[:300]))

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


def main() -> int:
    parser = argparse.ArgumentParser(description="云端 Qwen 引擎（DashScope 兼容接口，调用全留痕）")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--system", default=None, help="system 提示词")
    parser.add_argument("--prompt", default=None, help="user 提示词")
    parser.add_argument("--messages-file", default=None, help="JSON 文件：完整 messages 数组")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="只打印将发送的请求体，不联网")
    parser.add_argument("--no-log", action="store_true", help="本次调用不留痕")
    parser.add_argument("--json", action="store_true", help="输出完整 JSON（含日志路径）")
    args = parser.parse_args()

    try:
        messages = build_messages(args.system, args.prompt, args.messages_file)
    except (ValueError, OSError) as exc:
        print("参数错误：{}".format(exc))
        return 2

    if args.dry_run:
        preview = {"model": args.model, "temperature": args.temperature,
                   "max_tokens": args.max_tokens, "messages": messages,
                   "log_path_planned": str(LOG_DIR)}
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
