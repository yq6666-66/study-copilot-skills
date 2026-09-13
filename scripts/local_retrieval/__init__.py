# -*- coding: utf-8 -*-
"""学习副驾 · 端侧语义检索（Local Semantic Retrieval）。

在用户本地 AI PC 上用 bge-small-zh embedding 模型为错题队列与
Vault 笔记建立向量索引，供学习 Skill 在会话内做相似错题/知识点检索。
全部计算发生在本地，索引不出本机——这是「端云协同」中端侧的一环。

模块：
- embedder：embedding 工厂（fastembed 真实实现 / FakeEmbedder 测试实现）
- corpus：语料采集（错题队列 JSON + Markdown 笔记）
- embed_index：CLI 建索引
- semantic_search：CLI 语义查询
"""
