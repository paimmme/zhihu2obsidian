"""语义检索器."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..knowledge.embedder import Embedder

# ── Section type adjustment for search ranking ──────
# Boost/penalty by chunk section (semantic > verbatim)
SECTION_BOOST = {
    "AI 摘要": 0.06,
    "内容大纲": 0.04,
    "AI 总结": 0.04,
    "视频简介": -0.01,
    "字幕全文": -0.03,
}

PLATFORM_ICON = {
    "zhihu": "🤍",
    "bilibili": "📺",
    "xiaoyuzhou": "🎙",
    "": "📄",
}


def adjusted_score(r: dict) -> float:
    """Apply section boost to raw distance score."""
    score = 1.0 - r["distance"]
    section = r["metadata"].get("section", "")
    boost = SECTION_BOOST.get(section, 0.0)
    return round(score + boost, 4)


class Retriever:
    """语义检索器 — 从知识库检索最相关的内容."""

    def __init__(self, knowledge_dir: Path) -> None:
        self.embedder = Embedder(knowledge_dir)

    def search(self, query: str, n_results: int = 5, **filters) -> list[dict]:
        """语义搜索知识库 (原始结果, 无去重)."""
        filter_meta = None
        if filters:
            filter_meta = {}
            for key, val in filters.items():
                if val is not None:
                    filter_meta[key] = val

        results = self.embedder.search(query, n_results=n_results, filter_metadata=filter_meta)
        return results

    def search_grouped(self, query: str, n_results: int = 5, max_distance: float = 0.80, **filters) -> list[dict]:
        """Deduplicate by content_id, weighted by section type.

        1. Fetch enough raw results for grouping (min 2x, max 30)
        2. Group by content_id, keep best adjusted score per group
        3. Sort by adjusted score, return top N (or fewer if not enough)
        """
        pool = min(n_results * 2, 30)
        raw = self.search(query, n_results=pool, **filters)
        groups: dict = {}
        for r in raw:
            # Skip clearly unrelated noise
            if r["distance"] > max_distance:
                continue
            cid = r["metadata"].get("content_id", "unknown")
            adj = adjusted_score(r)
            entry = groups.get(cid)
            if not entry or adj > entry["best_score"]:
                groups[cid] = {"best_chunk": r, "best_score": adj}

        top = sorted(groups.values(), key=lambda g: g["best_score"], reverse=True)[:n_results]
        return [g["best_chunk"] for g in top]

    def search_with_context(self, query: str, n_results: int = 5) -> list[dict]:
        """带上下文的搜索结果 — 按 content_id 分组."""
        results = self.search(query, n_results=n_results)

        # Group by content_id for context
        grouped: dict = {}
        for r in results:
            cid = r["metadata"].get("content_id", "unknown")
            if cid not in grouped:
                grouped[cid] = {
                    "content_id": cid,
                    "title": r["metadata"].get("title", ""),
                    "url": r["metadata"].get("url", ""),
                    "author": r["metadata"].get("author", ""),
                    "chunks": [],
                    "avg_distance": 0,
                }
            grouped[cid]["chunks"].append(r)

        for g in grouped.values():
            avg = sum(c["distance"] for c in g["chunks"]) / len(g["chunks"]) if g["chunks"] else 0
            g["avg_distance"] = round(avg, 4)

        return sorted(grouped.values(), key=lambda x: x["avg_distance"])

    @property
    def stats(self) -> dict:
        return self.embedder.stats()
