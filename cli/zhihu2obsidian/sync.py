"""同步引擎 — 协调 API 调用 → 转换 → 写入."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .api import ZhihuAPI
from .config import Config
from .converter import build_full_markdown, html_to_markdown
from .images import download_all
from .models import Collection, CollectionItem, CollectionState, ContentResult, ImageRef, ItemState, SyncState


class SyncEngine:
    """增量同步引擎."""

    def __init__(self, config: Config, api: ZhihuAPI) -> None:
        self.config = config
        self.api = api
        self.state_path = config.output_path / ".state.json"
        self.state = SyncState.load(self.state_path)
        self.results = {
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "failed": [],
            "images_ok": 0,
            "images_fail": 0,
        }

    def sync_all(self, limit: int = 0, force: bool = False, dry_run: bool = False) -> dict:
        """同步所有收藏夹。"""
        print("📡 获取收藏夹列表...")
        collections = self.api.get_collections()
        print(f"   找到 {len(collections)} 个收藏夹\n")

        # Check for archived collections
        active_ids = {str(c.id) for c in collections}
        for coll_id, cstate in self.state.collections.items():
            if coll_id not in active_ids and not cstate.archived:
                print(f"  📦 收藏夹已消失（将归档）: {cstate.title}")
                cstate.archived = True

        for coll in collections:
            self._sync_collection(coll, limit, force, dry_run)

        self.state.last_sync = __import__("datetime").datetime.now().isoformat()
        if not dry_run:
            self.state.save(self.state_path)

        return self.results

    def sync_collection_by_id(self, collection_id: int, limit: int = 0, force: bool = False, dry_run: bool = False) -> dict:
        """同步指定收藏夹。"""
        collections = self.api.get_collections()
        coll = next((c for c in collections if c.id == collection_id), None)
        if not coll:
            raise ValueError(f"未找到收藏夹 #{collection_id}")
        self._sync_collection(coll, limit, force, dry_run)
        self.state.last_sync = __import__("datetime").datetime.now().isoformat()
        if not dry_run:
            self.state.save(self.state_path)
        return self.results

    def _sync_collection(self, coll: Collection, limit: int, force: bool, dry_run: bool) -> None:
        """同步单个收藏夹。"""
        coll_key = str(coll.id)
        safe_title = self._sanitize_path(coll.title)
        output_dir_name = f"{coll_key}__{safe_title}"
        output_dir = self.config.output_path / output_dir_name

        print(f"📁 {coll.title} ({coll.item_count} 条)")

        # Update or create collection state
        cstate = self.state.collections.get(coll_key)
        if not cstate:
            cstate = CollectionState(title=coll.title, output_dir=output_dir_name)
            self.state.collections[coll_key] = cstate
        else:
            cstate.title = coll.title

        # Get items
        items = self.api.get_collection_items(coll.id, max_items=limit or 0)
        if not items:
            print("   (空)\n")
            return

        for item in items:
            self._process_item(item, coll, cstate, output_dir, output_dir_name, force, dry_run)

        cstate.last_sync = __import__("datetime").datetime.now().isoformat()
        print()

    def _process_item(self, item: CollectionItem, coll: Collection, cstate: CollectionState,
                      output_dir: Path, output_dir_name: str, force: bool, dry_run: bool) -> None:
        """处理单条内容。"""
        cid = item.content_id
        istate = cstate.items.get(cid)

        # Check if we can skip — same URL + same API updated_time = unchanged
        if not force and istate:
            if istate.content_hash and istate.updated_time == item.updated_time:
                self.results["skipped"] += 1
                return

        # Fetch content HTML
        html = self._fetch_content(item)
        if not html:
            self.results["failed"].append({"id": cid, "url": item.url, "reason": "无法获取内容"})
            return

        # Convert to markdown
        markdown, images = html_to_markdown(html, cid)

        # Author name fallback
        author_name = item.author_name or "知乎用户"

        content_result = ContentResult(
            content_id=cid,
            title=item.question_title or cid,
            url=item.url,
            author_name=author_name,
            author_url=item.author_url,
            content_type=item.type,
            collection_title=coll.title,
            collection_id=coll.id,
            markdown=markdown,
            images=images,
            collect_time=item.collect_time,
            updated_time=item.collect_time,
        )

        full_md = build_full_markdown(item, content_result)
        content_hash = hashlib.sha256(full_md.encode()).hexdigest()

        # Check hash for update detection
        if not force and istate and istate.content_hash == content_hash:
            self.results["skipped"] += 1
            return

        file_name = f"{self._sanitize_path(item.question_title or cid)[:80]} - {cid}.md"
        file_path = output_dir / file_name

        if dry_run:
            action = "📄" if not istate else "🔄"
            print(f"  {action} {file_name} ({len(images)} 张图片)")
            self.results["added" if not istate else "updated"] += 1
            return

        # Write file
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path.write_text(full_md, encoding="utf-8")

        # Download images
        assets_dir = output_dir / "assets"
        img_results = download_all(images, assets_dir, self.config.image_concurrency)
        for _, ok in img_results:
            if ok:
                self.results["images_ok"] += 1
            else:
                self.results["images_fail"] += 1

        # Update state
        cstate.items[cid] = ItemState(
            url=item.url,
            title=item.question_title or cid,
            file_path=str(output_dir_name + "/" + file_name),
            content_hash=content_hash,
            updated_time=item.updated_time,
            content_version=(istate.content_version + 1) if istate else 1,
            exported_at=__import__("datetime").datetime.now().isoformat(),
        )

        if not istate:
            self.results["added"] += 1
        else:
            self.results["updated"] += 1

        action = "✅" if not istate else "🔄"
        print(f"  {action} {file_name} ({len(images)} 张图片)")

    def _fetch_content(self, item: CollectionItem) -> str | None:
        """获取内容 HTML。优先 API，降级爬取。"""
        if item.type == "answer" and item.answer_id:
            html = self.api.fetch_answer_content(item.answer_id)
            if html:
                return html
            print(f"    ⚠ 回答 API 返回空，尝试爬 HTML (question={item.question_id}, answer={item.answer_id})")
            if item.question_id and item.answer_id:
                return self.api.fetch_answer_html(item.question_id, item.answer_id)
        elif item.type == "article" and item.article_id:
            html = self.api.fetch_article_content(item.article_id)
            if html:
                return html
            print(f"    ⚠ 文章 API 失败，爬 HTML (article={item.article_id})")
            return self.api.fetch_article_html(item.article_id)
        return None

    @staticmethod
    def _sanitize_path(name: str) -> str:
        """清理文件名/目录名中的非法字符。"""
        for ch in '/\\:*?"<>|':
            name = name.replace(ch, "_")
        # Collapse whitespace
        name = " ".join(name.split())
        return name.strip() or "untitled"
