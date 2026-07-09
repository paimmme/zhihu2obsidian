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
