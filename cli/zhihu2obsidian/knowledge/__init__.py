"""智能知识库 — 知识构建 + 素材卡片 + 主题聚类."""

from __future__ import annotations

from .chunker import Chunk, chunk_all_markdowns

# Cards/Topics use optional deps (openai[deepseek], sklearn).
# Import lazily — CLI handlers already do this inside their functions.

__all__ = [
    "Chunk",
    "chunk_all_markdowns",
]
