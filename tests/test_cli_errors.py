# -*- coding: utf-8 -*-
"""CLI 错误消息体验回归测试：全部离线 monkeypatch，不发真实请求、不加载模型。"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))


# ---------- embed_index / semantic_search ----------

def test_embed_index_missing_model_gives_guidance(monkeypatch, capsys):
    import local_retrieval.embed_index as ei

    def boom(model_name=None):
        raise RuntimeError("端侧 embedding 依赖未就绪：请先运行 `python -m pip install fastembed`")

    monkeypatch.setattr(ei, "get_embedder", boom)
    monkeypatch.setattr(sys, "argv", ["embed_index.py", "--corpus", "demo-vault"])
    assert ei.main() == 2
    assert "pip install fastembed" in capsys.readouterr().out


def test_semantic_search_missing_index_actionable(tmp_path, monkeypatch, capsys):
    import local_retrieval.semantic_search as ss
    monkeypatch.setattr(sys, "argv", ["semantic_search.py", "--query", "x",
                                      "--index", str(tmp_path / "none")])
    assert ss.main() == 1
    out = capsys.readouterr().out
    assert "embed_index" in out  # 给出下一步命令


def test_semantic_search_missing_model_gives_guidance(tmp_path, monkeypatch, capsys):
    import local_retrieval.semantic_search as ss
    idx = tmp_path / ".index"
    idx.mkdir()
    (idx / "meta.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ss, "get_embedder",
                        lambda m=None: (_ for _ in ()).throw(RuntimeError("模型未就绪指引")))
    monkeypatch.setattr(sys, "argv", ["semantic_search.py", "--query", "x", "--index", str(idx)])
    assert ss.main() == 2
    assert "模型未就绪指引" in capsys.readouterr().out


# ---------- qwen_engine ----------

class Resp:
    def __init__(self, status):
        self.status_code = status
        self.text = '{"error":{"code":"invalid_api_key"}}'

    def json(self):
        return {}


def test_http_hints_are_actionable():
    import qwen_engine as qe
    assert "setx" in qe._http_action_hint(401)
    assert "限流" in qe._http_action_hint(429)
    assert "服务端" in qe._http_action_hint(503)


def test_401_error_message_includes_hint(monkeypatch):
    import qwen_engine as qe
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-fake-for-test")
    monkeypatch.setattr(qe, "_registry_key", lambda: None)
    monkeypatch.setattr(qe.requests, "post", lambda *a, **k: Resp(401))
    with pytest.raises(RuntimeError) as ei:
        qe.call_qwen([{"role": "user", "content": "x"}])
    msg = str(ei.value)
    assert "HTTP 401" in msg and "setx" in msg


def test_main_401_exit_2_with_hint(monkeypatch, capsys):
    import qwen_engine as qe
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-fake-for-test")
    monkeypatch.setattr(qe, "_registry_key", lambda: None)
    monkeypatch.setattr(qe.requests, "post", lambda *a, **k: Resp(401))
    monkeypatch.setattr(sys, "argv", ["qwen_engine.py", "--prompt", "hi"])
    assert qe.main() == 2
    assert "调用失败" in capsys.readouterr().out


def test_main_network_error_exit_3(monkeypatch, capsys):
    import qwen_engine as qe
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-fake-for-test")
    monkeypatch.setattr(qe, "_registry_key", lambda: None)

    def boom(*a, **k):
        raise qe.requests.ConnectionError("connection reset")

    monkeypatch.setattr(qe.requests, "post", boom)
    monkeypatch.setattr(sys, "argv", ["qwen_engine.py", "--prompt", "hi"])
    assert qe.main() == 3
    assert "网络异常" in capsys.readouterr().out
