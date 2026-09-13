# -*- coding: utf-8 -*-
"""Qwen 引擎离线单测：monkeypatch requests.post，绝不发起真实调用。"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import qwen_engine  # noqa: E402


class FakeResp:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text

    def json(self):
        return self._body


def ok_body(content="答案"):
    return {
        "choices": [{"message": {"role": "assistant", "content": content},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


@pytest.fixture()
def key_env(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test-key-123")


@pytest.fixture()
def tmp_log(monkeypatch, tmp_path):
    monkeypatch.setattr(qwen_engine, "LOG_DIR", tmp_path / "qwen")
    return tmp_path / "qwen"


def test_missing_key_exit_code(monkeypatch, capsys):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setattr(qwen_engine, "_registry_key", lambda: None)  # 本机注册表可能真有 Key，必须一并隔离
    sys.argv = ["qwen_engine.py", "--prompt", "测试"]
    rc = qwen_engine.main()
    out = capsys.readouterr().out
    assert rc == 2
    assert "DASHSCOPE_API_KEY" in out


def test_dry_run_no_network(monkeypatch, key_env, tmp_log, capsys):
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("dry-run 不应联网")

    monkeypatch.setattr(qwen_engine.requests, "post", boom)
    sys.argv = ["qwen_engine.py", "--dry-run", "--prompt", "测试"]
    rc = qwen_engine.main()
    out = capsys.readouterr().out
    assert rc == 0 and called["n"] == 0
    assert "测试" in out and "log_path_planned" in out
    assert not tmp_log.exists() or not list(tmp_log.glob("*.json"))


def test_call_writes_log_without_key(monkeypatch, key_env, tmp_log):
    monkeypatch.setattr(qwen_engine.requests, "post",
                        lambda *a, **k: FakeResp(body=ok_body("变式题")))
    result = qwen_engine.call_qwen([{"role": "user", "content": "出题"}])
    log_files = list(tmp_log.glob("*.json"))
    assert result["log_path"] and Path(result["log_path"]).exists()
    assert len(log_files) == 1
    record = json.loads(log_files[0].read_text(encoding="utf-8"))
    assert record["usage"]["total_tokens"] == 15
    assert "latency_ms" in record
    assert "sk-test-key-123" not in log_files[0].read_text(encoding="utf-8")


def test_no_log_flag(monkeypatch, key_env, tmp_log):
    monkeypatch.setattr(qwen_engine.requests, "post",
                        lambda *a, **k: FakeResp(body=ok_body()))
    result = qwen_engine.call_qwen([{"role": "user", "content": "x"}], log=False)
    assert result["log_path"] is None
    assert not tmp_log.exists() or not list(tmp_log.glob("*.json"))


def test_retry_on_429(monkeypatch, key_env, tmp_log):
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResp(status_code=429, text="rate limited")
        return FakeResp(body=ok_body("成功"))

    monkeypatch.setattr(qwen_engine.requests, "post", flaky)
    monkeypatch.setattr(qwen_engine.time, "sleep", lambda s: None)
    result = qwen_engine.call_qwen([{"role": "user", "content": "x"}])
    assert calls["n"] == 2 and result["content"] == "成功"


def test_secret_assertion_blocks_log(monkeypatch, key_env, tmp_log):
    def echo_key(*a, **k):
        # 模拟异常情形：响应里包含了 Key
        return FakeResp(body=ok_body("sk-test-key-123 泄漏"))

    monkeypatch.setattr(qwen_engine.requests, "post", echo_key)
    with pytest.raises(AssertionError):
        qwen_engine.call_qwen([{"role": "user", "content": "x"}])
