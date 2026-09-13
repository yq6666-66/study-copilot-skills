# -*- coding: utf-8 -*-
"""Embedding 工厂。

真实实现基于 fastembed 的 BAAI/bge-small-zh-v1.5（ONNX int8，CPU 可跑）。
首次运行自动下载模型；国内网络默认走 hf-mirror 镜像。
测试与冒烟用 FakeEmbedder（确定性哈希向量），不联网、不落模型。
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import List

MODEL_NAME = "BAAI/bge-small-zh-v1.5"
HF_MIRROR = "https://hf-mirror.com"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def models_dir() -> Path:
    d = _repo_root() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ensure_hf_mirror() -> None:
    """仅在用户未显式设置时启用镜像，不覆盖用户配置。"""
    os.environ.setdefault("HF_ENDPOINT", HF_MIRROR)


class FakeEmbedder:
    """确定性伪向量（SHA-256 哈希 → 单位向量），仅用于离线测试与 --fake 冒烟。"""

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vec = [digest[i % len(digest)] / 255.0 for i in range(self.dim)]
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]


def get_embedder(model_name: str = MODEL_NAME):
    """返回实现 .embed(texts) -> list[list[float]] 的 embedder。

    模型未就绪时抛出带中文安装指引的 RuntimeError，由调用方决定降级。
    模型已缓存时强制离线加载（断网/网络抖动不影响本地演示）。
    """
    try:
        _ensure_hf_mirror()
        from fastembed import TextEmbedding  # type: ignore
    except Exception as exc:  # pragma: no cover - 依赖缺失路径
        raise RuntimeError(
            "端侧 embedding 依赖未就绪：请先运行 "
            "`python -m pip install fastembed`。首次运行将从 "
            f"{os.environ.get('HF_ENDPOINT', HF_MIRROR)} 下载 {model_name} "
            "（约 100MB，缓存到仓库 models/ 目录）。原始原因：" + repr(exc)
        ) from exc

    try:
        model = TextEmbedding(model_name=model_name, cache_dir=str(models_dir()))
    except Exception:
        if not os.environ.get("HF_HUB_OFFLINE"):
            os.environ["HF_HUB_OFFLINE"] = "1"
            model = TextEmbedding(model_name=model_name, cache_dir=str(models_dir()))
        else:
            raise

    class _FastEmbedder:
        def embed(self, texts: List[str]) -> List[List[float]]:
            return [list(map(float, v)) for v in model.embed(texts)]

    return _FastEmbedder()
