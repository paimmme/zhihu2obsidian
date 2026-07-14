"""Data models."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Optional


@dataclasses.dataclass
class Collection:
    """知乎收藏夹."""
    id: int
    title: str
    item_count: int
    updated_time: int  # UNIX timestamp
    description: str = ""

    @classmethod
    def from_api(cls, data: dict) -> Collection:
        return cls(
            id=int(data["id"]),
            title=data["title"],
            item_count=data.get("item_count", 0),
            updated_time=data.get("updated_time", 0),
            description=data.get("description", ""),
        )


@dataclasses.dataclass
class CollectionItem:
    """收藏夹中的一条内容."""
    id: int
    type: str  # answer / article / video / pin / etc.
    url: str = ""
    question_title: str = ""
    question_id: Optional[int] = None
    answer_id: Optional[int] = None
    article_id: Optional[int] = None
    author_name: str = ""
    author_url: str = ""
    excerpt: str = ""
    collect_time: int = 0  # UNIX timestamp — when user bookmarked
    updated_time: int = 0  # UNIX timestamp — when content was last edited
    content_html: str = ""  # fetched from content API

    @property
    def content_id(self) -> str:
        if self.type == "answer":
            return f"answer_{self.id}"
        elif self.type == "article":
            return f"article_{self.id}"
        return f"{self.type}_{self.id}"

    @classmethod
    def from_api(cls, data: dict) -> CollectionItem:
        item_type = data.get("type", "")
        base = cls(id=int(data.get("id", 0)), type=item_type)

        if item_type == "answer":
            question = data.get("question", {}) or {}
            base.question_title = question.get("title", "")
            base.question_id = int(question["id"]) if question.get("id") else None
            base.answer_id = base.id
            base.url = f"https://www.zhihu.com/question/{base.question_id}/answer/{base.answer_id}"
            base.excerpt = (data.get("excerpt") or "")

        elif item_type == "article":
            base.article_id = base.id
            base.question_title = data.get("excerpt_title", "")
            base.url = f"https://zhuanlan.zhihu.com/p/{base.article_id}"
            base.excerpt = (data.get("excerpt") or "")

        else:
            base.question_title = data.get("excerpt_title", "") or data.get("title", "")
            base.url = data.get("url", "")

        author = data.get("author", {}) or {}
        base.author_name = author.get("name", "")
        base.author_url = f"https://www.zhihu.com/people/{author.get('url_token', '')}" if author.get("url_token") else ""

        base.collect_time = data.get("collect_time", 0)
        base.updated_time = data.get("updated_time", 0)
        return base


@dataclasses.dataclass
class ContentResult:
    """完整的内容（含已转换的 Markdown 和图片引用）."""
    content_id: str
    title: str
    url: str
    author_name: str
    author_url: str
    content_type: str  # answer / article
    collection_title: str
    collection_id: int
    markdown: str
    images: list[ImageRef]
    collect_time: int
    updated_time: int
    content_quality: str = ""  # full_text / subtitle / summary / intro_only / too_short
    account: str = "default"


@dataclasses.dataclass
class ImageRef:
    """图片引用."""
    url: str
    filename: str  # hash.ext
    content_id: str  # parent content id


@dataclasses.dataclass
class SyncState:
    """增量同步状态."""
    version: int = 2
    last_sync: str = ""
    collections: dict[str, CollectionState] = dataclasses.field(default_factory=dict)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(dataclasses.asdict(self), ensure_ascii=False, indent=2))

    @classmethod
    def load(cls, path: Path) -> SyncState:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        # Recursively deserialize nested dataclasses
        collections = {}
        for cid, cdata in data.get("collections", {}).items():
            items = {}
            for iid, idata in cdata.get("items", {}).items():
                items[iid] = ItemState(**idata)
            cdata["items"] = items
            collections[cid] = CollectionState(**cdata)
        data["collections"] = collections
        return cls(**data)


@dataclasses.dataclass
class CollectionState:
    """收藏夹同步状态."""
    title: str
    output_dir: str
    last_sync: str = ""
    account: str = "default"
    archived: bool = False
    items: dict[str, ItemState] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class ItemState:
    """单条内容同步状态."""
    url: str
    title: str
    file_path: str
    content_hash: str  # SHA-256 of full markdown
    updated_time: int
    content_version: int = 1
    content_quality: str = ""
    account: str = "default"
    exported_at: str = ""
