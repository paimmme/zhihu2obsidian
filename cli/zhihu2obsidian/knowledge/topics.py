"""主题聚类 — ChromaDB 向量 + KMeans + LLM 主题页."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import requests
from sklearn.cluster import KMeans

from .embedder import Embedder
from .cards import CardExtractor, MaterialCard

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"
N_TOPICS = 15  # 初始主题数（~5 篇/主题）

TOPIC_GENERATION_PROMPT = """你是一名内容分析师。以下是某个主题簇的代表素材，请生成该主题的结构化描述。

返回格式：只返回 JSON，不要其他内容。

JSON 字段说明：
- title: 主题标题（简洁，8-20 字，如 "AI编程工具与开发者生态"）
- summary: 主题摘要（50-150 字，概述该主题讨论什么）
- keywords: 关键词列表（3-8 个）
- viewpoints: 该主题下的主要观点/立场列表
- counterpoints: 反方观点或争议点列表
- writing_ideas: 基于此主题可写的文章方向/角度列表

注意：基于提供的素材内容，不要编造。如果素材足够丰富，可以提炼出观点冲突。"""


@dataclass
class TopicPage:
    """主题页 — 一个主题簇的结构化描述."""

    id: str = ""  # topic_001
    title: str = ""
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    viewpoints: list[str] = field(default_factory=list)
    counterpoints: list[str] = field(default_factory=list)
    writing_ideas: list[str] = field(default_factory=list)

    # Source statistics
    content_count: int = 0
    source_platforms: list[str] = field(default_factory=list)
    content_ids: list[str] = field(default_factory=list)

    # Representative content (for display)
    representative_contents: list[dict] = field(default_factory=list)

    # Metadata
    cluster_id: int = 0
    created_at: str = ""


class TopicClusterer:
    """主题聚类 — 基于 KMeans + LLM 的主题簇生成."""

    def __init__(
        self,
        embedder: Embedder,
        knowledge_dir: Path,
        api_key: str = "",
        model: str = DEFAULT_MODEL,
        n_topics: int = N_TOPICS,
    ) -> None:
        self.embedder = embedder
        self.topics_dir = knowledge_dir / "topics"
        self.topics_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.topics_dir / "index.json"
        self.api_key = api_key
        self.model = model
        self.n_topics = n_topics
        self.cards_dir = knowledge_dir / "cards"

    # ── Clustering ──────────────────────────────────

    def cluster(self) -> list[TopicPage]:
        """全流程：获取向量 → KMeans → 生成主题页."""
        print(f"🔢 获取 {self.embedder.count()} 个向量...")
        results = self.embedder.collection.get(
            include=["embeddings", "metadatas", "documents"]
        )
        embeddings = np.array(results["embeddings"])
        ids = results["ids"]
        metadatas = results["metadatas"]
        documents = results["documents"]

        if len(embeddings) < self.n_topics:
            self.n_topics = max(3, len(embeddings) // 3)

        print(f"🧮 KMeans 聚类 (n={self.n_topics})...")
        kmeans = KMeans(n_clusters=self.n_topics, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings)

        # Group by cluster
        clusters: dict[int, dict[str, Any]] = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = {
                    "ids": [],
                    "metadatas": [],
                    "documents": [],
                    "distances": [],
                    "content_ids": set(),
                }
            clusters[label]["ids"].append(ids[i])
            clusters[label]["metadatas"].append(metadatas[i])
            clusters[label]["documents"].append(documents[i])
            clusters[label]["distances"].append(
                float(np.linalg.norm(embeddings[i] - kmeans.cluster_centers_[label]))
            )
            cid = metadatas[i].get("content_id", "")
            if cid:
                clusters[label]["content_ids"].add(cid)

        print(f"📦 生成 {len(clusters)} 个主题页...\n")
        topics: list[TopicPage] = []
        for label in sorted(clusters.keys()):
            cluster = clusters[label]
            # Sort by distance to centroid
            sorted_idx = np.argsort(cluster["distances"])

            # Representative chunks (top 5 closest to centroid)
            rep_chunks = []
            for idx in sorted_idx[:5]:
                m = cluster["metadatas"][idx]
                rep_chunks.append({
                    "text": cluster["documents"][idx][:200] if cluster["documents"][idx] else "",
                    "content_id": m.get("content_id", ""),
                    "title": m.get("title", ""),
                    "author": m.get("author", ""),
                    "platform": m.get("platform", ""),
                    "section": m.get("section", ""),
                })

            # Load related cards for more context
            related_cards = self._load_cards(cluster["content_ids"])

            # Generate topic page with LLM
            topic = self._generate_topic(
                label=label,
                rep_chunks=rep_chunks,
                cards=related_cards,
                content_ids=list(cluster["content_ids"]),
                content_count=len(cluster["content_ids"]),
            )
            topics.append(topic)
            print(f"  [{label+1}/{self.n_topics}] {topic.title} ({topic.content_count} 篇)")

        self._save_index(topics)
        return topics

    def _load_cards(self, content_ids: set[str]) -> list[MaterialCard]:
        """加载相关的素材卡片."""
        cards: list[MaterialCard] = []
        if not self.cards_dir.exists():
            return cards
        for cid in content_ids:
            cf = self.cards_dir / f"{cid}.json"
            if cf.exists():
                try:
                    cards.append(MaterialCard(**json.loads(cf.read_text())))
                except Exception:
                    pass
        return cards

    def _generate_topic(
        self,
        label: int,
        rep_chunks: list[dict],
        cards: list[MaterialCard],
        content_ids: list[str],
        content_count: int,
    ) -> TopicPage:
        """用 LLM 生成主题页."""
        # Build context
        context_parts = []
        for chunk in rep_chunks:
            context_parts.append(
                f"[{chunk['platform']}] {chunk['title']} — {chunk['author']}\n"
                f"{chunk['text']}"
            )

        # Add card viewpoints if available
        for card in cards[:3]:
            if card.core_points:
                for cp in card.core_points[:2]:
                    context_parts.append(f"[观点] {cp}")
            if card.counterpoints:
                for cp in card.counterpoints[:2]:
                    context_parts.append(f"[反方] {cp}")

        context = "\n\n".join(context_parts)
        truncated = context[:4000]

        user_prompt = f"素材内容：\n\n{truncated}" if truncated else "素材内容不足，请根据已有信息生成主题描述。"

        # Call LLM
        title_fallback = f"主题簇 {label+1}"
        if self.api_key:
            try:
                resp = requests.post(
                    DEEPSEEK_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": TOPIC_GENERATION_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1500,
                        "stream": False,
                    },
                    timeout=60,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    result_text = data["choices"][0]["message"]["content"].strip()
                    parsed = self._parse_llm_output(result_text)
                    if parsed:
                        title_fallback = parsed.get("title", title_fallback)
                        topic = TopicPage(
                            id=f"topic_{label+1:03d}",
                            title=title_fallback,
                            summary=parsed.get("summary", ""),
                            keywords=parsed.get("keywords", []),
                            viewpoints=parsed.get("viewpoints", []),
                            counterpoints=parsed.get("counterpoints", []),
                            writing_ideas=parsed.get("writing_ideas", []),
                            content_count=content_count,
                            source_platforms=list(set(
                                c["platform"] for c in rep_chunks if c.get("platform")
                            )),
                            content_ids=content_ids[:10],
                            representative_contents=rep_chunks[:3],
                            cluster_id=label,
                            created_at=datetime.now().isoformat(),
                        )
                        self._save_topic(topic)
                        return topic
            except Exception:
                pass

        # Fallback: generate without LLM
        topic = TopicPage(
            id=f"topic_{label+1:03d}",
            title=title_fallback,
            summary=self._keyword_summary(rep_chunks),
            keywords=self._extract_keywords(rep_chunks, cards),
            content_count=content_count,
            source_platforms=list(set(
                c["platform"] for c in rep_chunks if c.get("platform")
            )),
            content_ids=content_ids[:10],
            representative_contents=rep_chunks[:3],
            cluster_id=label,
            created_at=datetime.now().isoformat(),
        )
        self._save_topic(topic)
        return topic

    @staticmethod
    def _parse_llm_output(text: str) -> dict | None:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _keyword_summary(rep_chunks: list[dict]) -> str:
        titles = [c.get("title", "") for c in rep_chunks if c.get("title")]
        if titles:
            return "相关素材: " + " | ".join(titles[:3])
        return ""

    @staticmethod
    def _extract_keywords(rep_chunks: list[dict], cards: list[MaterialCard]) -> list[str]:
        keywords: list[str] = []
        seen: set[str] = set()
        for card in cards:
            for t in card.topics:
                if t not in seen:
                    seen.add(t)
                    keywords.append(t)
                    if len(keywords) >= 8:
                        return keywords
        return keywords[:8]

    # ── Persistence ─────────────────────────────────

    def _save_topic(self, topic: TopicPage) -> None:
        tf = self.topics_dir / f"{topic.id}.json"
        tf.write_text(
            json.dumps(asdict(topic), ensure_ascii=False, indent=2, default=str)
        )

    def _save_index(self, topics: list[TopicPage]) -> None:
        index = []
        for t in topics:
            index.append({
                "id": t.id,
                "title": t.title,
                "keywords": t.keywords,
                "content_count": t.content_count,
                "source_platforms": t.source_platforms,
            })
        self.index_file.write_text(
            json.dumps(index, ensure_ascii=False, indent=2, default=str)
        )

    # ── Query ───────────────────────────────────────

    def list_topics(self) -> list[dict]:
        if self.index_file.exists():
            return json.loads(self.index_file.read_text())
        return []

    def get_topic(self, topic_id: str) -> TopicPage | None:
        tf = self.topics_dir / f"{topic_id}.json"
        if tf.exists():
            try:
                return TopicPage(**json.loads(tf.read_text()))
            except Exception:
                return None
        return None

    def search_by_topic(self, query: str, top_n: int = 5) -> list[TopicPage]:
        """简单关键词匹配所有主题页."""
        q = query.lower()
        scored: list[tuple[TopicPage, int]] = []
        for f in self.topics_dir.glob("topic_*.json"):
            try:
                topic = TopicPage(**json.loads(f.read_text()))
            except Exception:
                continue
            score = 0
            if q in topic.title.lower():
                score += 5
            for kw in topic.keywords:
                if q in kw.lower():
                    score += 3
            for vp in topic.viewpoints:
                if q in vp.lower():
                    score += 2
            if q in topic.summary.lower():
                score += 2
            if score:
                scored.append((topic, score))
        scored.sort(key=lambda x: -x[1])
        return [t for t, _ in scored[:top_n]]

    def reset(self) -> None:
        for f in self.topics_dir.glob("topic_*.json"):
            f.unlink()
        if self.index_file.exists():
            self.index_file.unlink()
