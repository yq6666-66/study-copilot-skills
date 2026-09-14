# -*- coding: utf-8 -*-
"""云端引擎服务商无关配置的离线单测：端点拼接 / 模型覆盖 / Key 候选链（不联网）。"""
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import qwen_engine as qe  # noqa: E402


def test_endpoint_override_and_default(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    assert qe.endpoint() == qe.DEFAULT_ENDPOINT
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1/")
    assert qe.endpoint() == "https://api.deepseek.com/v1/chat/completions"
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    assert qe.endpoint() == "http://localhost:11434/v1/chat/completions"


def test_default_model_priority(monkeypatch):
    for var in ("OPENAI_MODEL", "LLM_MODEL"):
        monkeypatch.delenv(var, raising=False)
    assert qe.default_model() == qe.DEFAULT_MODEL
    monkeypatch.setenv("LLM_MODEL", "kimi-k2")
    assert qe.default_model() == "kimi-k2"
    monkeypatch.setenv("OPENAI_MODEL", "deepseek-chat")
    assert qe.default_model() == "deepseek-chat"  # OPENAI_MODEL 优先


def test_key_candidate_chain_order(monkeypatch):
    for var in qe.KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(qe, "_registry_key", lambda: None)
    assert qe._key_candidates() == []
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-legacy")
    assert qe._key_candidates() == ["sk-legacy"]
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    assert qe._key_candidates() == ["sk-openai", "sk-legacy"]  # OPENAI 优先、去重
    monkeypatch.setenv("LLM_API_KEY", "sk-openai")  # 与已有候选重复则不追加
    assert qe._key_candidates() == ["sk-openai", "sk-legacy"]
    # 防泄漏断言覆盖全部候选
    with pytest.raises(AssertionError):
        qe._assert_no_secret("reply contains sk-legacy")


def test_call_without_key_raises_actionable_error(monkeypatch):
    for var in qe.KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(qe, "_registry_key", lambda: None)
    with pytest.raises(RuntimeError) as ei:
        qe.call_qwen([{"role": "user", "content": "hi"}])
    assert "OPENAI_API_KEY" in str(ei.value)
