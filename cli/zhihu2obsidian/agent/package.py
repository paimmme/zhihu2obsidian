"""写作素材包 — 素材搜索 + LLM 组织 → 结构化写作包."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

import requests

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"

PACKAGE_PROMPT = """你是一个写作策划助手。用户想写一篇回答/文章，以下是可用的素材。

请综合分析这些素材，生成一份结构化写作素材包。

返回格式：只返回 JSON，不要其他内容。

JSON 字段说明：
- core_viewpoints: 核心观点列表（2-4个，综合多个素材后提炼的核心主张，每个一句话）
- argument_chain: 论据链，每个对象含:
  - point: 观点/主张
  - evidence: 论据/证据原文
  - source_title: 来源标题
  - source_author: 来源作者
  - evidence_type: 类型（数据/案例/逻辑推理/引用/个人经历）
- case_stories: 可用的案例/故事列表, 每个含:
  - story: 故事描述
  - source: 来源
  - usage: 适合用在文章的哪个部分
- key_quotes: 金句引用列表, 每个含:
  - quote: 原文金句
  - source: 来源
  - context: 这句话的背景/上下文
- counterpoints: 需要回应的反方观点列表（如果素材中有提及）
- writing_angles: 推荐写作角度（2-3个不同的切入方向）
- outline: 文章大纲（3-5个章节，每个含标题和要点）

注意事项：
1. 区分作者原创观点和引用外部来源
2. 标记有争议或片面的内容
3. 论据链应覆盖核心观点的正反两面
4. 不编造素材中没有的内容"""


@dataclass
class WritingPackage:
    """结构化写作素材包."""

    topic: str = ""

    # Core material
    core_viewpoints: list[str] = field(default_factory=list)
    argument_chain: list[dict] = field(default_factory=list)
    case_stories: list[dict] = field(default_factory=list)
    key_quotes: list[dict] = field(default_factory=list)

    # Writing support
    counterpoints: list[str] = field(default_factory=list)
    writing_angles: list[str] = field(default_factory=list)
    outline: list[dict] = field(default_factory=list)

    # Draft (optional, when with_draft=True)
    draft_title: str = ""
    draft: str = ""

    # Sources
    sources: list[dict] = field(default_factory=list)
    source_topics: list[str] = field(default_factory=list)

    # Metadata
    created_at: str = ""


class WritingPackageBuilder:
    """素材包构建器 — 从知识库+卡片+主题生成结构化写作包."""

    def __init__(
        self,
        api_key: str = "",
        model: str = DEFAULT_MODEL,
        retriever=None,
        cards_dir=None,
        topics_dir=None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.retriever = retriever
        self.cards_dir = cards_dir
        self.topics_dir = topics_dir

    def build(
        self,
        topic: str,
        personal_take: str = "",
        n_results: int = 5,
        with_draft: bool = False,
    ) -> WritingPackage:
        """全流程：检索素材 → LLM 组织 → 返回结构化包.

        Args:
            topic: 写作主题/问题
            personal_take: 用户个人观点（可选）
            n_results: 检索素材数
            with_draft: 是否同时生成初稿

        Returns:
            WritingPackage 对象
        """
        # ── 1. 检索素材 ──
        context_parts = []
        sources = []
        source_topics: set[str] = set()
        used_content_ids: set[str] = set()

        # 1a. ChromaDB 语义搜索
        if self.retriever:
            search_results = self.retriever.search_with_context(
                topic, n_results=n_results
            )
            for sr in search_results:
                title = sr.get("title", "")
                author = sr.get("author", "")
                platform = sr.get("platform", "")
                cid = sr.get("content_id", "")
                chunks = sr.get("chunks", [])
                if cid:
                    used_content_ids.add(cid)
                for ch in chunks[:2]:
                    text = ch.get("text", "")
                    if text:
                        context_parts.append(
                            f"[{platform}] {title} ({author}):\n{text[:400]}"
                        )
                sources.append({
                    "title": title,
                    "author": author,
                    "platform": platform,
                    "content_id": cid,
                    "type": "semantic_search",
                })

        # 1b. 素材卡片
        if self.cards_dir and self.cards_dir.exists():
            matched_cards = self._search_cards(topic, n_results)
            for card in matched_cards:
                cid = card.get("content_id", "")
                if cid in used_content_ids:
                    continue
                used_content_ids.add(cid)
                title = card.get("title", "")
                author = card.get("author", "")
                platform = card.get("platform", "")
                # Add core points, arguments, case_stories, key_quotes
                for cp in card.get("core_points", [])[:2]:
                    context_parts.append(f"[观点/{platform}] {title}: {cp}")
                for arg in card.get("arguments", [])[:2]:
                    if isinstance(arg, dict):
                        context_parts.append(
                            f"[论据/{platform}] {arg.get('point', '')} — {arg.get('evidence', '')[:200]}"
                        )
                for cs in card.get("case_stories", [])[:2]:
                    if isinstance(cs, str):
                        context_parts.append(f"[案例/{platform}] {cs[:200]}")
                    elif isinstance(cs, dict):
                        context_parts.append(
                            f"[案例/{platform}] {cs.get('content', cs.get('title', ''))[:200]}"
                        )
                for kq in card.get("key_quotes", [])[:1]:
                    if isinstance(kq, str):
                        context_parts.append(f"[金句/{platform}] {kq}")
                # Add card topics
                for t in card.get("topics", [])[:3]:
                    source_topics.add(t)
                sources.append({
                    "title": title,
                    "author": author,
                    "platform": platform,
                    "content_id": cid,
                    "type": "card",
                })

        # 1c. 主题页
        if self.topics_dir and self.topics_dir.exists():
            matching_topics = self._search_topics(topic)
            for tp in matching_topics:
                title = tp.get("title", "")
                source_topics.add(title)
                for vp in tp.get("viewpoints", [])[:2]:
                    context_parts.append(f"[主题/{title}] {vp}")
                for wi in tp.get("writing_ideas", [])[:2]:
                    context_parts.append(f"[选题/{title}] {wi}")

        # ── 2. LLM 组织 → 素材包 ──
        package = self._generate_package(
            topic=topic,
            context="\n\n".join(context_parts),
            personal_take=personal_take,
            with_draft=with_draft,
        )
        package.topic = topic
        package.sources = sources
        package.source_topics = list(source_topics)
        package.created_at = datetime.now().isoformat()

        return package

    def _search_cards(self, query: str, top_n: int) -> list[dict]:
        """关键词匹配卡片."""
        if not self.cards_dir:
            return []
        q = query.lower()
        scored: list[tuple[dict, int]] = []
        for f in sorted(self.cards_dir.glob("*.json")):
            if f.name == "manifest.json":
                continue
            try:
                card = json.loads(f.read_text())
            except Exception:
                continue
            score = 0
            for t in card.get("topics", []):
                if q in t.lower():
                    score += 4
            for cp in card.get("core_points", []):
                if q in cp.lower():
                    score += 3
            for arg in card.get("arguments", []):
                if isinstance(arg, dict):
                    for v in arg.values():
                        if q in str(v).lower():
                            score += 1
            title = card.get("title", "")
            if q in title.lower():
                score += 2
            if score:
                scored.append((card, score))
        scored.sort(key=lambda x: -x[1])
        return [c for c, _ in scored[:top_n]]

    def _search_topics(self, query: str, top_n: int = 3) -> list[dict]:
        """关键词匹配主题页."""
        if not self.topics_dir:
            return []
        q = query.lower()
        scored: list[tuple[dict, int]] = []
        for f in sorted(self.topics_dir.glob("topic_*.json")):
            try:
                tp = json.loads(f.read_text())
            except Exception:
                continue
            score = 0
            if q in tp.get("title", "").lower():
                score += 5
            for kw in tp.get("keywords", []):
                if q in kw.lower():
                    score += 3
            for vp in tp.get("viewpoints", []):
                if q in vp.lower():
                    score += 2
            if q in tp.get("summary", "").lower():
                score += 2
            if score:
                scored.append((tp, score))
        scored.sort(key=lambda x: -x[1])
        return [t for t, _ in scored[:top_n]]

    def _generate_package(
        self,
        topic: str,
        context: str,
        personal_take: str = "",
        with_draft: bool = False,
    ) -> WritingPackage:
        """LLM 生成素材包."""
        fallback = WritingPackage(topic=topic, created_at=datetime.now().isoformat())

        if not self.api_key or not context:
            # Minimal fallback
            fallback.core_viewpoints = ["搜索到相关素材，可设置 API Key 自动生成素材包"]
            return fallback

        user_prompt = f"""## 写作目标

我想写一篇关于以下话题的回答/文章：

{topic}

"""

        if personal_take:
            user_prompt += f"""
## 我的个人观点/立场

{personal_take}
"""

        user_prompt += f"""
## 可用素材

{context[:5000]}
"""

        if with_draft:
            user_prompt += """
请额外生成初稿：在 outline 基础上扩展为完整文章（800-1500字），
结合素材中的观点和论据，语言自然口语化，适合知乎风格。
在 JSON 中增加字段：
- draft_title: 文章标题
- draft: 完整初稿
- draft_word_count: 字数估算
"""

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
                        {"role": "system", "content": PACKAGE_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 3000,
                    "stream": False,
                },
                timeout=90,
            )
        except requests.RequestException as e:
            fallback.core_viewpoints = [f"API 调用失败: {e}"]
            return fallback

        if resp.status_code != 200:
            fallback.core_viewpoints = [f"API 错误: HTTP {resp.status_code}"]
            return fallback

        try:
            data = resp.json()
            result_text = data["choices"][0]["message"]["content"].strip()
            parsed = self._parse_json(result_text)
            if not parsed:
                fallback.core_viewpoints = ["LLM 输出解析失败"]
                return fallback
            return WritingPackage(
                topic=topic,
                core_viewpoints=parsed.get("core_viewpoints", []),
                argument_chain=parsed.get("argument_chain", []),
                case_stories=parsed.get("case_stories", []),
                key_quotes=parsed.get("key_quotes", []),
                counterpoints=parsed.get("counterpoints", []),
                writing_angles=parsed.get("writing_angles", []),
                outline=parsed.get("outline", []),
                draft_title=parsed.get("draft_title", "") if with_draft else "",
                draft=parsed.get("draft", "") if with_draft else "",
                created_at=datetime.now().isoformat(),
            )
        except Exception as e:
            fallback.core_viewpoints = [f"处理失败: {e}"]
            return fallback

    @staticmethod
    def _parse_json(text: str) -> dict | None:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def render_text(self, package: WritingPackage) -> str:
        """渲染素材包为可读文本."""
        lines = [f"# 📦 写作素材包: {package.topic}", ""]

        # Core viewpoints
        if package.core_viewpoints:
            lines.append("## 💡 核心观点")
            for vp in package.core_viewpoints:
                lines.append(f"- {vp}")
            lines.append("")

        # Argument chain
        if package.argument_chain:
            lines.append("## 🔗 论据链")
            for i, arg in enumerate(package.argument_chain, 1):
                point = arg.get("point", "")
                evidence = arg.get("evidence", "")
                source = arg.get("source_title", "")
                lines.append(f"  **{point}**")
                if evidence:
                    lines.append(f"  > {evidence}")
                if source:
                    lines.append(f"  _来源: {source}_")
                lines.append("")

        # Case stories
        if package.case_stories:
            lines.append("## 📖 案例库")
            for cs in package.case_stories:
                story = cs.get("story", "") if isinstance(cs, dict) else str(cs)
                source = cs.get("source", "") if isinstance(cs, dict) else ""
                usage = cs.get("usage", "") if isinstance(cs, dict) else ""
                lines.append(f"- {story}")
                if source:
                    lines.append(f"  _来源: {source}_")
                if usage:
                    lines.append(f"  _推荐用法: {usage}_")
            lines.append("")

        # Key quotes
        if package.key_quotes:
            lines.append("## 💬 金句")
            for kq in package.key_quotes:
                quote = kq.get("quote", "") if isinstance(kq, dict) else str(kq)
                source = kq.get("source", "") if isinstance(kq, dict) else ""
                lines.append(f"> {quote}")
                if source:
                    lines.append(f"  — {source}")
            lines.append("")

        # Counterpoints
        if package.counterpoints:
            lines.append("## ⚡ 反方观点")
            for cp in package.counterpoints:
                lines.append(f"- {cp}")
            lines.append("")

        # Writing angles
        if package.writing_angles:
            lines.append("## ✍️ 写作角度")
            for wa in package.writing_angles:
                lines.append(f"- {wa}")
            lines.append("")

        # Outline
        if package.outline:
            lines.append("## 📋 文章大纲")
            for section in package.outline:
                if isinstance(section, dict):
                    lines.append(f"### {section.get('title', '')}")
                    for pt in section.get("points", []):
                        lines.append(f"- {pt}")
                else:
                    lines.append(f"- {section}")
            lines.append("")

        # Draft
        if package.draft:
            lines.append("---")
            lines.append("")
            lines.append(f"## ✍️ 初稿: {package.draft_title or ''}")
            lines.append("")
            lines.append(package.draft)
            lines.append(f"\n_(字数: ~{len(package.draft)}字)_")

        # Sources
        if package.sources:
            lines.append("---")
            lines.append("## 📚 使用素材")
            for s in package.sources:
                t = s.get("title", s.get("content_id", "?"))
                a = s.get("author", "")
                p = s.get("platform", "")
                lines.append(f"- [{p}] {t} ({a})")

        return "\n".join(lines)


# ── Late imports ──────────────────────────────────
import json
