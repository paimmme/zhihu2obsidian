"""P3: 核心模块导入测试."""


def test_core_imports() -> None:
    """核心模块 (无可选依赖) 应可导入."""
    from zhihu2obsidian.api import ZhihuAPI
    from zhihu2obsidian.sync import SyncEngine
    from zhihu2obsidian.converter import ObsidianConverter
    from zhihu2obsidian.config import Config
    from zhihu2obsidian.__main__ import main
    assert ZhihuAPI is not None
    assert SyncEngine is not None
    assert ObsidianConverter is not None
    assert Config is not None
    assert callable(main)


def test_knowledge_chunker_import() -> None:
    """知识库分块 (无 sklearn/LLM 依赖) 可导入."""
    from zhihu2obsidian.knowledge.chunker import Chunk, chunk_all_markdowns, chunk_markdown_file
    assert Chunk is not None
    assert callable(chunk_all_markdowns)
    assert callable(chunk_markdown_file)


def test_embedder_import() -> None:
    """Embedder (chromadb 可选依赖) 可导入."""
    from zhihu2obsidian.knowledge.embedder import Embedder
    assert Embedder is not None


def test_topics_import() -> None:
    """主题聚类 (sklearn 可选依赖) 在直接导入时可用."""
    from zhihu2obsidian.knowledge.topics import TopicClusterer, TopicPage
    assert TopicClusterer is not None
    assert TopicPage is not None


def test_cards_import() -> None:
    """素材卡片 (openai 可选依赖) 在直接导入时可用."""
    from zhihu2obsidian.knowledge.cards import CardExtractor, MaterialCard
    assert CardExtractor is not None
    assert MaterialCard is not None


def test_tree_and_server_core_imports() -> None:
    """知识树与分析器核心模块可导入."""
    from zhihu2obsidian.tree.builder import KnowledgeTreeBuilder
    from zhihu2obsidian.tree.matcher import KnowledgeTreeMatcher
    from zhihu2obsidian.server.analyzer import SelectionAnalyzer

    assert KnowledgeTreeBuilder is not None
    assert KnowledgeTreeMatcher is not None
    assert SelectionAnalyzer is not None


def test_export_import() -> None:
    """export 模块能加载。"""
    from zhihu2obsidian.export import SourceItem, ChunkRecord, MaterialCard, run_export, detect_quality, clean_zhihu_body
    assert SourceItem is not None
    assert ChunkRecord is not None
    assert MaterialCard is not None
    assert callable(run_export)
    assert callable(detect_quality)

    # 质量检测
    assert detect_quality("bilibili", "短") == "too_short"
    assert detect_quality("bilibili", "A" * 100 + "B" * 100) == "intro_only"
    assert detect_quality("bilibili", "内容\n\n## 字幕全文\n\n" + "字" * 600) == "subtitle"
    assert detect_quality("zhihu", "A" * 200) == "full_text"
    assert detect_quality("zhihu", "短") == "too_short"

    # 正文清洗 (旧格式兼容)
    dirty = "> 来源: https://zhuanlan.zhihu.com/p/123\n# 标题\n\n正文\n> 回答 by [author](url)"
    cleaned = clean_zhihu_body(dirty)
    assert "来源:" not in cleaned
    assert "回答 by" not in cleaned
    assert "正文" in cleaned


def test_build_full_markdown_clean() -> None:
    """build_full_markdown 正文不含冗余 boilerplate。"""
    from zhihu2obsidian.converter import build_full_markdown, build_frontmatter
    from zhihu2obsidian.models import CollectionItem, ContentResult, ImageRef

    item = CollectionItem(id=123, type="answer")
    result = ContentResult(
        content_id="answer_123",
        title="测试标题",
        url="https://zhihu.com/q/1/a/123",
        author_name="测试作者",
        author_url="https://zhihu.com/people/test",
        content_type="answer",
        collection_title="我的收藏",
        collection_id=99,
        markdown="这是正文内容。\n\n第二段正文。",
        images=[],
        collect_time=0,
        updated_time=0,
        content_quality="full_text",
    )
    md = build_full_markdown(item, result)
    # 正文不含冗余 boilerplate（旧版 > 来源、# 标题、> 回答 by、底部 ---）
    assert "> 来源:" not in md
    assert "# 测试标题" not in md
    assert "> 回答 by" not in md
    # 前端 --- 分隔符正常（frontmatter 边界）
    assert md.startswith("---")
    # 正文内容保留
    assert "这是正文内容。" in md
    assert "第二段正文。" in md
    # frontmatter 保留
    assert "title: 测试标题" in md
    assert "content_quality: full_text" in md
