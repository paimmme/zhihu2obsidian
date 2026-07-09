"""HTML → Obsidian Markdown 转换器."""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from markdownify import MarkdownConverter

from .models import CollectionItem, ContentResult, ImageRef


class ObsidianConverter(MarkdownConverter):
    """定制化的 Markdown 转换器 — 适用 Obsidian 语法."""

    def convert_img(self, el, text, parent_tags):
        """图片 → ![[assets/content_id/hash.ext]]"""
        src = el.get("src", "")
        if not src or src.startswith("data:"):
            return ""

        clean_url = src.split("?")[0]
        ext = self._ext_from_url(clean_url)
        url_hash = self._hash_url(clean_url)

        self._pending_images.append({
            "url": src if src.startswith("http") else f"https:{src}",
            "hash": url_hash,
            "ext": ext,
        })

        return f"![[assets/{self._content_id}/{url_hash}.{ext}]]"

    @staticmethod
    def _hash_url(url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()[:16]

    @staticmethod
    def _ext_from_url(url: str) -> str:
        match = re.search(r"\.(jpg|jpeg|png|gif|webp|bmp|svg)(\?|$)", url, re.IGNORECASE)
        return match.group(1).lower() if match else "jpg"

    def convert_a(self, el, text, parent_tags):
        href = el.get("href", "")
        if not text.strip():
            return ""
        return f"[{text}]({href})"

    def convert_li(self, el, text, parent_tags):
        parent = el.parent
        if parent is not None and parent.name == "ol":
            return f"1. {text}"
        return f"- {text}"

    def convert_pre(self, el, text, parent_tags):
        if not text:
            return ""
        code = el.find("code")
        if code:
            lang = ""
            cls = code.get("class", [])
            if cls:
                lang = cls[0].replace("language-", "") if isinstance(cls[0], str) else ""
            content = code.get_text()
        else:
            lang = ""
            content = el.get_text()
        return f"\n```{lang}\n{content.strip()}\n```\n\n"

    def convert_hr(self, el, text, parent_tags):
        return "\n\n---\n\n"


def html_to_markdown(html: str, content_id: str) -> tuple[str, list[ImageRef]]:
    """将知乎 HTML 内容转换为 Obsidian Markdown，返回 (markdown, images)"""
    converter = ObsidianConverter(heading_style="ATX", bullets="-", strip=["script", "style"])
    converter._pending_images = []
    converter._content_id = content_id

    markdown = converter.convert(html)

    images = []
    for img in converter._pending_images:
        images.append(ImageRef(
            url=img["url"],
            filename=f"{img['hash']}.{img['ext']}",
            content_id=content_id,
        ))

    return markdown.strip(), images


def build_frontmatter(
    title: str,
    url: str,
    author: str,
    author_url: str,
    content_type: str,
    content_id: str,
    collection_title: str,
    collection_id: int,
    collect_time: int,
) -> str:
    """生成 YAML frontmatter."""

    def esc(val: str) -> str:
        val = val.replace("\\", "\\\\").replace('"', '\\"')
        if any(c in val for c in ":,#[]{}&\n"):
            return f'"{val}"'
        return val

    lines = ["---"]
    lines.append(f"title: {esc(title)}")
    lines.append(f"url: {esc(url)}")
    lines.append(f"author: {esc(author)}")
    lines.append("platform: zhihu")
    lines.append(f"source: 知乎收藏")
    lines.append(f"collection: {esc(collection_title)}")
    lines.append(f"collection_id: {collection_id}")
    lines.append(f"content_type: {content_type}")
    lines.append(f"content_id: {content_id}")
    if collect_time:
        import datetime
        dt = datetime.datetime.fromtimestamp(collect_time, tz=datetime.timezone.utc)
        lines.append(f"created: {dt.strftime('%Y-%m-%d')}")
    import datetime
    lines.append(f"exported_at: {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    lines.append("tags:")
    lines.append("  - zhihu")
    lines.append(f"  - {esc(collection_title)}")
    lines.append("---")
    return "\n".join(lines)


def build_full_markdown(item: CollectionItem, result: ContentResult) -> str:
    """组装完整的 Markdown 文件内容."""
    parts = []

    parts.append(build_frontmatter(
        title=result.title,
        url=result.url,
        author=result.author_name,
        author_url=result.author_url,
        content_type=result.content_type,
        content_id=result.content_id,
        collection_title=result.collection_title,
        collection_id=result.collection_id,
        collect_time=result.collect_time,
    ))

    parts.append(f"\n> 来源: {result.url}\n")
    parts.append(f"# {result.title}")

    if result.author_name:
        parts.append(f"\n> 回答 by [{result.author_name}]({result.author_url})")

    parts.append("")
    parts.append(result.markdown)
    parts.append("")
    parts.append("---")
    parts.append(f"原文链接：[{result.title}]({result.url})")

    return "\n".join(parts)
