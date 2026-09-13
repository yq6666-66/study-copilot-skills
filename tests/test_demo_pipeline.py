# -*- coding: utf-8 -*-
"""demo_pipeline 离线测试：注入 FakeEmbedder 与假 chat，全程不联网、不调真实模型。"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from demo_pipeline import pick_item, run_pipeline  # noqa: E402
from local_retrieval.embedder import FakeEmbedder  # noqa: E402

QUEUE = {
    "schemaVersion": "1.1", "recordType": "ReviewQueue", "generatedAt": "2026-09-13",
    "items": [
        {"id": "a1", "subject": "数学一", "topic": "级数", "errorCause": "判别法混用",
         "errorCauseStatus": "hypothesis", "nextRetestDate": None, "retestOffsetDays": 7,
         "status": "due", "masteryEvidence": []},
        {"id": "b2", "subject": "408-操作系统", "topic": "死锁-银行家算法", "errorCause": "安全性检测漏分支",
         "errorCauseStatus": "confirmed", "nextRetestDate": "2026-09-14", "retestOffsetDays": None,
         "status": "retesting", "masteryEvidence": []},
    ],
}


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    (tmp_path / "30-知识").mkdir(parents=True)
    (tmp_path / "30-知识" / "错题队列.json").write_text(
        json.dumps(QUEUE, ensure_ascii=False), encoding="utf-8")
    note = tmp_path / "30-知识" / "错题笔记"
    note.mkdir()
    (note / "死锁.md").write_text("# 死锁簇\n银行家算法安全性检测。", encoding="utf-8")
    return tmp_path


def fake_chat_factory():
    calls = []

    def chat(messages, model="qwen-flash"):
        calls.append(messages)
        return {"content": "【变式题】……", "usage": {"total_tokens": 42},
                "log_path": "logs/qwen/fake.json", "model": model}
    return chat, calls


def test_pick_item_defaults_retesting_first():
    assert pick_item(QUEUE["items"])["id"] == "b2"
    assert pick_item(QUEUE["items"], "a1")["id"] == "a1"
    with pytest.raises(KeyError):
        pick_item(QUEUE["items"], "nope")


def test_pipeline_full_steps_offline(vault: Path):
    chat, calls = fake_chat_factory()
    report = run_pipeline(vault, embedder=FakeEmbedder(), chat=chat)
    # 四步结构
    assert [s["step"] for s in report["steps"]] == ["端侧索引", "端侧检索", "云端 Qwen"]
    # 锚点默认 retesting 条目
    assert report["item"]["id"] == "b2"
    # 召回排除自身
    assert all(r["doc_id"] != "review:b2" for r in report["recalled"])
    # 云端被调一次且 prompt 含错因
    assert len(calls) == 1 and "安全性检测漏分支" in calls[0][1]["content"]
    assert report["cloud"]["mode"] == "live" and report["cloud"]["usage"]["total_tokens"] == 42


def test_pipeline_dry_cloud_never_calls(vault: Path):
    def boom(messages, **kw):
        raise AssertionError("dry-cloud 不应调用云端")

    report = run_pipeline(vault, embedder=FakeEmbedder(), chat=boom, dry_cloud=True)
    assert report["cloud"]["mode"] == "dry-preview"
    assert "安全性检测漏分支" in report["cloud"]["prompt"]


def test_pipeline_reuses_existing_index(vault: Path):
    chat, calls = fake_chat_factory()
    r1 = run_pipeline(vault, embedder=FakeEmbedder(), chat=chat)
    idx = vault / "30-知识" / ".index"
    assert (idx / "meta.json").exists()
    r2 = run_pipeline(vault, embedder=FakeEmbedder(), chat=chat)
    assert r1["steps"][0]["docs"] == r2["steps"][0]["docs"]
    assert r2["steps"][0]["rebuilt"] is False


def test_pipeline_rebuilds_on_model_mismatch(vault: Path):
    """fake 建的索引遇到真实模型（维度不同）必须自动重建而非维度崩溃。"""

    class OtherEmbedder(FakeEmbedder):
        model_tag = "other-model"

        def __init__(self):
            super().__init__(dim=16)

    chat, calls = fake_chat_factory()
    run_pipeline(vault, embedder=FakeEmbedder(), chat=chat)  # dim64 / tag=fake
    r = run_pipeline(vault, embedder=OtherEmbedder(), chat=chat)
    assert r["steps"][0]["rebuilt"] is True
    assert r["recalled"]  # 重建后检索正常，不报维度错误


def test_pipeline_missing_corpus(vault: Path):
    with pytest.raises(FileNotFoundError):
        run_pipeline(vault / "不存在", embedder=FakeEmbedder(), chat=lambda m: {})
