"""Knowledge tree and selection analyzer behavior."""

from __future__ import annotations

import json
from pathlib import Path


class FakeRetriever:
    def search(self, query: str, n_results: int = 5, **filters):
        return [
            {
                "text": "AI 编程工具能提升开发效率，但也会让基础能力退化，需要保留人工判断。",
                "metadata": {
                    "content_id": "answer_123",
                    "title": "如何看待 AI 编程工具",
                    "author": "测试作者",
                    "platform": "zhihu",
                },
                "distance": 0.12,
                "score": 0.88,
            },
            {
                "text": "Cursor 工作流适合快速探索代码库，再由工程师做质量检查。",
                "metadata": {
                    "content_id": "answer_456",
                    "title": "Cursor 使用经验",
                    "author": "另一个作者",
                    "platform": "zhihu",
                },
                "distance": 0.28,
                "score": 0.72,
            },
        ][:n_results]


def test_tree_builder_builds_stable_nodes_and_applies_overrides(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / ".knowledge"
    topics_dir = knowledge_dir / "topics"
    topics_dir.mkdir(parents=True)
    (topics_dir / "topic_001.json").write_text(
        json.dumps(
            {
                "id": "topic_001",
                "title": "主题簇 1",
                "summary": "关于 AI 编程效率和开发者判断的素材。",
                "keywords": ["AI 编程", "Cursor"],
                "viewpoints": ["AI 编程提升效率"],
                "counterpoints": ["过度依赖会弱化基础能力"],
                "writing_ideas": ["从效率和能力退化的矛盾切入"],
                "content_ids": ["answer_123"],
                "representative_contents": [
                    {
                        "content_id": "answer_123",
                        "title": "如何看待 AI 编程工具",
                        "author": "测试作者",
                        "platform": "zhihu",
                        "text": "AI 编程工具能提升开发效率。",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (knowledge_dir / "tree").mkdir()
    (knowledge_dir / "tree" / "overrides.yaml").write_text(
        "rename:\n  topic_001: AI 编程工具\nparent:\n  node_topic_001: node_tech\n",
        encoding="utf-8",
    )

    from zhihu2obsidian.tree.builder import KnowledgeTreeBuilder

    tree = KnowledgeTreeBuilder(knowledge_dir).build()

    assert tree["version"] == 1
    assert tree["nodes"][0]["id"] == "node_topic_001"
    assert tree["nodes"][0]["title"] == "AI 编程工具"
    assert tree["nodes"][0]["parent_id"] == "node_tech"
    assert tree["nodes"][0]["content_ids"] == ["answer_123"]
    assert (knowledge_dir / "tree" / "index.json").exists()


def test_selection_analyzer_returns_tree_matches_sources_risks_and_suggestions(tmp_path: Path) -> None:
    tree_dir = tmp_path / ".knowledge" / "tree"
    tree_dir.mkdir(parents=True)
    (tree_dir / "index.json").write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at": "2026-07-13T00:00:00",
                "nodes": [
                    {
                        "id": "node_ai_coding",
                        "title": "AI 编程工具",
                        "summary": "围绕 AI 编程助手、开发者效率、工程实践的内容集合。",
                        "keywords": ["AI 编程", "Cursor", "效率"],
                        "parent_id": None,
                        "children": [],
                        "source_topic_ids": ["topic_001"],
                        "content_ids": ["answer_123", "answer_456"],
                        "representative_chunks": [],
                        "confidence": 0.8,
                        "created_at": "2026-07-13T00:00:00",
                        "updated_at": "2026-07-13T00:00:00",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    from zhihu2obsidian.server.analyzer import SelectionAnalyzer

    analyzer = SelectionAnalyzer(
        knowledge_dir=tmp_path / ".knowledge",
        retriever=FakeRetriever(),
        api_key="",
    )
    result = analyzer.analyze(
        text="AI 编程工具能提升开发效率，但也可能让人过度依赖。",
        url="https://www.zhihu.com/question/1/answer/2",
        page_title="知乎问题",
        question_title="如何看待 AI 编程？",
        author="知乎作者",
    )

    assert result["matched_tree_nodes"][0]["node_id"] == "node_ai_coding"
    assert result["matched_tree_nodes"][0]["path"] == ["AI 编程工具"]
    assert result["similar_sources"][0]["content_id"] == "answer_123"
    assert result["writing_suggestions"]
    assert result["risks"][0]["level"] in {"medium", "high"}
