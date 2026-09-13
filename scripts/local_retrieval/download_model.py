# -*- coding: utf-8 -*-
"""预下载端侧 embedding 模型（约 100MB，缓存到仓库 models/）。

用法：python scripts/local_retrieval/download_model.py
国内网络默认走 hf-mirror（可用环境变量 HF_ENDPOINT 覆盖）。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from local_retrieval.embedder import MODEL_NAME, get_embedder, models_dir  # noqa: E402


def main() -> int:
    print("开始下载/校验模型：{}".format(MODEL_NAME))
    started = time.time()
    embedder = get_embedder(MODEL_NAME)
    _ = embedder.embed(["下载验证"])  # 触发完整初始化
    print("完成。缓存目录：{}，耗时 {:.1f}s".format(models_dir(), time.time() - started))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
