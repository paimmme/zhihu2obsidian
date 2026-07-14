"""Bilibili 收藏夹适配器."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import requests

from ..platforms import register
from ..platforms.base import Platform, PlatformCollection, PlatformItem
from .bilibili_content import build_video_md

API_BASE = "https://api.bilibili.com"

REQUIRED_COOKIES = {"SESSDATA"}
RATE_LIMIT = 1.2  # seconds between requests


def _rate_limit(last: float) -> float:
    now = time.time()
    elapsed = now - last
    if elapsed < RATE_LIMIT:
        time.sleep(RATE_LIMIT - elapsed)
    return time.time()


def _bapi(path: str, cookies: dict, params: dict | None = None) -> dict:
    """Bilibili API 调用."""
    h = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://space.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }
    r = requests.get(f"{API_BASE}{path}", headers=h, cookies=cookies, params=params, timeout=15)
    data = r.json()
    code = data.get("code", -1)
    if code != 0:
        msg = data.get("message", "?")
        if code == -101:
            raise PermissionError(f"Bilibili 登录失效 (-101 {msg})")
        if code == -400:
            raise ValueError(f"Bilibili 参数错误 (-400 {msg})")
        raise RuntimeError(f"Bilibili API 错误 ({code}): {msg}")
    return data.get("data", {})


@register("bilibili")
class BilibiliPlatform(Platform):
    """Bilibili 收藏夹适配器."""

    def __init__(self, config, cookie_file: str):
        super().__init__(config, cookie_file)
        self._mid: str | None = None

    @property
    def name(self) -> str:
        return "bilibili"

    def check_auth(self) -> tuple[bool, str]:
        try:
            data = _bapi("/x/web-interface/nav", self.cookies)
            if data.get("isLogin"):
                uname = data.get("uname", "?")
                self._mid = str(data.get("mid", ""))
                return True, f"Bilibili 已登录: {uname}"
            return False, "Bilibili 未登录"
        except PermissionError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Bilibili 认证失败: {e}"

    def list_collections(self) -> list[PlatformCollection]:
        """列出收藏夹（创建的 + 收藏的）。"""
        # 先获取 mid
        if not self._mid:
            nav = _bapi("/x/web-interface/nav", self.cookies)
            self._mid = str(nav.get("mid", ""))
            if not self._mid:
                raise RuntimeError("无法获取用户 mid")

        cols: list[PlatformCollection] = []

        # 创建的收藏夹
        created = _bapi("/x/v3/fav/folder/created/list-all", self.cookies,
                        {"up_mid": int(self._mid)})
        for f in created.get("list", []):
            cols.append(PlatformCollection(
                id=str(f["id"]),
                title=f["title"],
                item_count=f.get("media_count", 0),
                description=f.get("intro", ""),
                updated_time=f.get("mtime", 0),
                platform="bilibili",
            ))

        # 收藏的收藏夹 (可选，非关键路径)
        try:
            pn = 1
            while True:
                collected = _bapi("/x/v3/fav/folder/collected/list", self.cookies,
                                  {"pn": pn, "ps": 20})
                for f in collected.get("list", []):
                    cols.append(PlatformCollection(
                        id=str(f["id"]),
                        title=f["title"],
                        item_count=f.get("media_count", 0),
                        description=f.get("intro", ""),
                        updated_time=f.get("mtime", 0),
                        platform="bilibili",
                    ))
                if not collected.get("has_more"):
                    break
                pn += 1
        except Exception:
            pass  # 收藏的收藏夹非必需

        return cols

    def get_items(self, collection: PlatformCollection) -> list[PlatformItem]:
        """获取收藏夹内内容."""
        items: list[PlatformItem] = []
        pn = 1

        while True:
            data = _bapi("/x/v3/fav/resource/list", self.cookies, {
                "media_id": collection.id,
                "pn": pn,
                "ps": 20,
                "platform": "web",
                "type": 0,
                "tid": 0,
                "order": "mtime",
                "web_location": "333.1387",
            })
            for r in data.get("medias", []):
                item = self._parse_media(r)
                if item:
                    items.append(item)

            if not data.get("has_more"):
                break
            pn += 1
            _rate_limit(pn)

        return items

    def _parse_media(self, r: dict) -> PlatformItem | None:
        """解析单条收藏内容."""
        rtype = r.get("type", 0)
        title = r.get("title", "") or ""
        bvid = r.get("bvid", "")
        intro = r.get("intro", "") or ""
        fav_time = r.get("fav_time", 0)
        ctime = r.get("ctime", 0)  # content create time

        if rtype == 2:  # Video
            cid = f"video_{bvid}"
            url = f"https://www.bilibili.com/video/{bvid}"
            # Get author info
            upper = r.get("upper", {})
            author = upper.get("name", "")
            author_mid = upper.get("mid", "")
            author_url = f"https://space.bilibili.com/{author_mid}" if author_mid else ""

            return PlatformItem(
                id=cid,
                type="video",
                title=title,
                url=url,
                author_name=author,
                author_url=author_url,
                description=intro,
                collect_time=fav_time,
                updated_time=ctime,
                platform="bilibili",
                extra={
                    "bvid": bvid,
                    "aid": r.get("aid", 0),
                    "duration": r.get("duration", ""),
                },
            )

        elif rtype == 12:  # Article / Column
            cvid = r.get("id", "") or r.get("cvid", "")
            cid = f"article_{cvid}"
            url = f"https://www.bilibili.com/read/cv{cvid}"
            author = r.get("author", {}).get("name", "")
            author_mid = r.get("author", {}).get("mid", "")
            author_url = f"https://space.bilibili.com/{author_mid}" if author_mid else ""

            return PlatformItem(
                id=cid,
                type="article",
                title=title,
                url=url,
                author_name=author,
                author_url=author_url,
                description=intro,
                collect_time=fav_time,
                updated_time=ctime,
                platform="bilibili",
                extra={"cvid": cvid, "aid": r.get("aid", 0)},
            )

        # Other types (audio, album) — skip for now
        return None

    def get_content(self, item: PlatformItem) -> str | None:
        """获取内容 HTML。"""
        if item.type == "article":
            return self._fetch_article(item)
        elif item.type == "video":
            return self._video_to_html(item)
        return None

    def _fetch_article(self, item: PlatformItem) -> str | None:
        """获取专栏文章 HTML."""
        cvid = item.extra.get("cvid", "")
        if not cvid:
            return None
        try:
            data = _bapi("/x/article/viewinfo", self.cookies, {"id": cvid})
            html = data.get("content", "")
            if not html:
                return None
            # Wrap with metadata
            title = item.title
            author = item.author_name
            tags_html = ""
            for t in data.get("tags", []):
                tags_html += f'<span class="tag">{t.get("name", "")}</span> '
            return f"""<h1>{title}</h1>
<p>作者: <a href="{item.author_url}">{author}</a></p>
<p>{','.join(t.get('name','') for t in data.get('tags',[]))}</p>
<hr>
{html}"""
        except Exception:
            return None

    def _video_to_html(self, item: PlatformItem) -> str | None:
        """视频 → 富文本 markdown（字幕 + AI 摘要 + 描述）。"""
        bvid = item.extra.get("bvid", "")
        if not bvid:
            return None
        try:
            sessdata = self.cookies.get("SESSDATA", "")
            return build_video_md(bvid, sessdata) or None
        except Exception:
            return None


def sync_bilibili(
    config, bp, account="default",
    collection_id=None, limit=0, force=False,
):
    """同步 Bilibili 收藏夹到 vault."""
    import datetime
    import hashlib
    import html as html_mod
    import re

    from ..converter import build_frontmatter, html_to_markdown
    from ..models import CollectionState, SyncState, ItemState
    from ..sync import _state_path_for

    if not config.vault:
        print("❌ vault 路径未设置")
        import sys; sys.exit(1)

    ok, msg = bp.check_auth()
    if not ok:
        print(f"❌ {msg}")
        print("   请先运行: zhihu2obsidian auth login --platform bilibili")
        import sys; sys.exit(1)
    print(f"✅ {msg}\n")

    out_root = config.output_path / "bilibili"
    out_root.mkdir(parents=True, exist_ok=True)
    state_file = _state_path_for(out_root, account)
    state = SyncState.load(state_file)

    cols = bp.list_collections()
    if collection_id:
        cols = [c for c in cols if c.id == collection_id]

    total_new = total_fail = total_skip = 0

    for col in cols:
        from ..utils import sanitize_path
        safe_title = sanitize_path(col.title)
        cname = f"{col.id}__{safe_title}"
        cdir = out_root / cname
        cdir.mkdir(parents=True, exist_ok=True)

        print(f"📁 {col.title} ({col.item_count} 条)")
        cstate = state.collections.get(col.id)
        if not cstate:
            cstate = CollectionState(title=col.title, output_dir=cname, account=account)
            state.collections[col.id] = cstate

        try:
            items = bp.get_items(col)
        except Exception as e:
            print(f"   ⚠ 获取内容列表失败: {e}")
            print("   跳过此收藏夹")
            continue
        lim = limit or len(items)

        for item in items[:lim]:
            cid = item.content_id
            istate = cstate.items.get(cid)

            if not force and istate and istate.content_hash:
                # Check if content was updated since last sync
                item_updated = getattr(item, 'updated_time', None) or 0
                istate_updated = getattr(istate, 'updated_time', None) or 0
                if item_updated > istate_updated:
                    print(f"   ♻️  {item.title[:50]:.50s} (内容已更新)")
                else:
                    total_skip += 1
                    print(f"   ⏭️  {item.title[:50]:.50s} (已有)")
                    continue

            content = bp.get_content(item)
            if not content:
                total_fail += 1
                print(f"   ❌ {item.title[:50]:.50s} (无内容)")
                continue

            # Video returns markdown directly, article returns HTML
            if content.strip().startswith("<"):
                md_text, images = html_to_markdown(content, cid)
            else:
                md_text = content
                now_iso = datetime.datetime.now().isoformat()

            # Detect content quality
            word_count = len(md_text)
            if "字幕全文" in md_text or "CC 字幕" in md_text:
                content_quality = "subtitle"
            elif "AI 摘要" in md_text or word_count >= 200:
                content_quality = "summary"
            elif word_count >= 80:
                content_quality = "intro_only"
            else:
                content_quality = "too_short"

            # Use unified build_frontmatter
            extra_fields = {"collected": ""}
            if item.collect_time:
                extra_fields["collected"] = datetime.datetime.fromtimestamp(item.collect_time).strftime("%Y-%m-%d")
            frontmatter = build_frontmatter(
                title=item.title, url=item.url,
                author=item.author_name,
                platform="bilibili", content_quality=content_quality,
                collection_title=col.title,
                account=account,
                extra=extra_fields,
            )

            full_md = frontmatter + "\n\n" + md_text
            safe_fname = re.sub(r'[\\/:*?"<>|]', "_", f"{item.title[:60]} - {cid}.md")
            fpath = cdir / safe_fname
            fpath.write_text(full_md, encoding="utf-8")

            cstate.items[cid] = ItemState(
                url=item.url,
                title=item.title,
                file_path=f"bilibili/{cname}/{safe_fname}",
                content_hash=hashlib.sha256(full_md.encode()).hexdigest()[:16],
                updated_time=item.updated_time,
                content_quality=content_quality,
                account=account,
                exported_at=now_iso,
            )
            total_new += 1
            print(f"   ✅ {item.title[:60]:.60s}")

        # Detect un-favorited items (in old state but no longer in API response)
        api_ids = {it.content_id for it in items}
        removed = [iid for iid in list(cstate.items) if iid not in api_ids]
        for rid in removed:
            old = cstate.items[rid]
            print(f"   📦 已取消收藏: {old.title[:50]:.50s}")
            old_path = out_root.parent / old.file_path
            if old_path.exists():
                old_path.unlink()
            del cstate.items[rid]
            total_skip += 1

        state.save(state_file)

    print(f"\n{'='*40}")
    print(f"📊 Bilibili 同步完成:")
    print(f"   新增: {total_new}")
    print(f"   跳过: {total_skip}")
    print(f"   失败: {total_fail}")
    print(f"   输出: {out_root}")
    return {"added": total_new, "skipped": total_skip, "failed": total_fail}


def _linkify_bilibili(text: str) -> str:
    """简单链接化 — 将 B 站文本中的 BV 号转为链接."""
    import re as _re
    text = _re.sub(
        r'(BV[a-zA-Z0-9]{10})',
        r'<a href="https://www.bilibili.com/video/\1">\1</a>',
        text,
    )
    return text
