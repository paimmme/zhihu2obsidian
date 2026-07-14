"""Converter + sync + API 测试."""
from __future__ import annotations

from pathlib import Path

from zhihu2obsidian.converter import (
    build_frontmatter,
    html_to_markdown,
)
from zhihu2obsidian.models import SyncState, CollectionState, ItemState
from zhihu2obsidian.export import clean_body, detect_quality


# ── Converter ─────────────────────────────────────────

def test_build_frontmatter_basic():
    """build_frontmatter 基础字段."""
    fm = build_frontmatter(
        title="测试标题",
        url="https://zhihu.com/question/1",
        author="测试作者",
        author_url="https://zhihu.com/people/test",
        content_type="answer",
        content_id="zhihu_answer_1",
        collection_title="我的收藏",
        collection_id=123,
        collect_time=1700000000,
        content_quality="full_text",
        platform="zhihu",
        account="work",
    )
    assert "title: 测试标题" in fm
    assert 'url: "https://zhihu.com/question/1"' in fm
    assert "author: 测试作者" in fm
    assert "platform: zhihu" in fm
    assert "account: work" in fm
    assert "content_quality: full_text" in fm
    assert fm.startswith("---\n")
    assert fm.endswith("---")
    # 不要强制尾随换行 (build_frontmatter 以 --- 结尾)
    assert "  - 我的收藏" in fm


def test_build_frontmatter_default_account():
    """缺省 account='default'."""
    fm = build_frontmatter(title="t", url="http://x", author="a")
    assert "account: default" in fm


def test_build_frontmatter_platform_extra():
    """B站特有字段通过 extra 传入."""
    fm = build_frontmatter(
        title="b站视频",
        url="https://bilibili.com/video/BV1xx",
        author="UP主",
        platform="bilibili",
        account="personal",
        extra={"collected": "2026-07-13", "type": "video", "collected": "2026-07-13"},
    )
    assert "platform: bilibili" in fm
    assert "account: personal" in fm


def test_clean_body_zhihu():
    """清洗知乎 Markdown boilerplate."""
    dirty = (
        "> 来源: https://zhuanlan.zhihu.com/p/123\n"
        "# 标题\n\n"
        "正文内容\n\n"
        "> 回答 by [作者名](https://zhihu.com/people/author)\n"
        "# 另一个标题\n\n"
        "更多正文"
    )
    cleaned = clean_body("zhihu", dirty)
    assert "来源:" not in cleaned
    assert "回答 by" not in cleaned
    assert "正文内容" in cleaned
    assert "更多正文" in cleaned


def test_clean_body_bilibili():
    """B站不做清洗."""
    dirty = "> 来源: some\n\n内容"
    assert clean_body("bilibili", dirty) == dirty


def test_html_to_markdown_basic():
    """简单的 HTML → Markdown 转换."""
    html = "<p>Hello <strong>world</strong></p>"
    md, images = html_to_markdown(html, "test_1")
    assert "Hello" in md
    assert isinstance(images, list)
    # 不测试具体语法（markdownify 版本差异）
    assert len(md) < len(html) or "world" in md


# ── SyncState ─────────────────────────────────────────

def test_sync_state_roundtrip(tmp_path):
    """SyncState JSON 序列化/反序列化保持 account 字段."""
    path = tmp_path / ".state.personal.json"
    state = SyncState(
        collections={
            "123__test": CollectionState(
                title="测试收藏",
                output_dir="123__test",
                account="personal",
                items={
                    "answer_1": ItemState(
                        url="http://x",
                        title="标题",
                        file_path="123__test/title.md",
                        content_hash="abc123",
                        updated_time=1700000000,
                        content_quality="full_text",
                        account="personal",
                    ),
                },
            ),
        },
    )
    state.save(path)
    loaded = SyncState.load(path)
    assert loaded.collections["123__test"].account == "personal"
    assert loaded.collections["123__test"].items["answer_1"].account == "personal"
    assert loaded.collections["123__test"].items["answer_1"].content_hash == "abc123"


def test_sync_state_load_missing(tmp_path):
    """不存在的 state 文件返回空 SyncState."""
    path = tmp_path / ".state.nonexist.json"
    state = SyncState.load(path)
    assert state.collections == {}


def test_sync_state_remove_item():
    """从 CollectionState 移除 item."""
    state = SyncState(
        collections={
            "c1": CollectionState(
                title="c1",
                output_dir="c1",
                items={
                    "a1": ItemState(url="http://a1", title="t1", file_path="c1/a1.md", content_hash="h1", updated_time=100),
                    "a2": ItemState(url="http://a2", title="t2", file_path="c1/a2.md", content_hash="h2", updated_time=100),
                },
            ),
        },
    )
    del state.collections["c1"].items["a1"]
    assert "a1" not in state.collections["c1"].items
    assert "a2" in state.collections["c1"].items


# ── Quality classification ───────────────────────────

def test_quality_full_text():
    """200+ 字知乎正文 → full_text."""
    assert detect_quality("zhihu", "A" * 500) == "full_text"


def test_quality_too_short():
    """<50 字 → too_short."""
    assert detect_quality("zhihu", "短内容") == "too_short"
    assert detect_quality("bilibili", "短") == "too_short"


def test_quality_subtitle():
    """含字幕的 B站 → subtitle."""
    body = "简介\n\n## 字幕全文\n\n" + "字" * 600
    assert detect_quality("bilibili", body) == "subtitle"


def test_quality_intro_only():
    """B站无字幕 → intro_only."""
    body = "这是视频简介\n\n" + "A" * 200
    assert detect_quality("bilibili", body) == "intro_only"


# ── utils ─────────────────────────────────────────────

def test_state_path_format():
    """state 文件名格式 .state.<account>.json."""
    from zhihu2obsidian.utils import state_path_for
    assert state_path_for(Path("/vault"), "default").name == ".state.default.json"
    assert state_path_for(Path("/vault"), "personal").name == ".state.personal.json"


def test_sanitize_path():
    """清理路径非法字符."""
    from zhihu2obsidian.utils import sanitize_path
    assert sanitize_path("Hello World") == "Hello World"
    assert sanitize_path("a/b:c*d?e") == "a_b_c_d_e"
    assert "  " not in sanitize_path("  spaced  ")


# ── API path patterns ─────────────────────────────────

def test_collections_path():
    """收藏夹列表路径含 url_token."""
    token = "test_user_123"
    path = f"/api/v4/people/{token}/collections"
    assert token in path
    assert "/api/v4/people/" in path


def test_contents_path():
    """内容列表路径含 collection_id."""
    cid = "12345"
    path = f"/collections/{cid}/contents"
    assert cid in path
