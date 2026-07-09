"""Zhihu API 封装 — 收藏夹列表/内容/详情."""

from __future__ import annotations

import random
import time
from typing import Optional

import requests

from .models import Collection, CollectionItem

BASE_URL = "https://www.zhihu.com/api/v4"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www.zhihu.com/",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.zhihu.com",
}


class ZhihuAPI:
    """知乎 API 客户端 — 所有请求携带 Cookie."""

    def __init__(self, cookie_jar, rate_min: float = 1.0, rate_max: float = 3.0) -> None:
        self._cookies = cookie_jar.to_dict() if hasattr(cookie_jar, 'to_dict') else cookie_jar
        self._rate_min = rate_min
        self._rate_max = rate_max
        self._session = requests.Session()
        self._session.headers.update(HEADERS)

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """带限流的请求."""
        time.sleep(random.uniform(self._rate_min, self._rate_max))
        kwargs.setdefault("timeout", 30)
        r = self._session.request(method, url, cookies=self._cookies, **kwargs)

        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", "5"))
            print(f"  ⚠ 限流，等待 {retry_after}s...")
            time.sleep(retry_after)
            r = self._session.request(method, url, cookies=self._cookies, **kwargs)

        return r

    def _resolve_url_token(self) -> str:
        """获取当前用户的 url_token."""
        r = self._request("GET", f"{BASE_URL}/me")
        if r.status_code != 200:
            raise RuntimeError(f"获取用户信息失败: HTTP {r.status_code} {r.text[:200]}")
        return r.json()["url_token"]

    def get_collections(self) -> list[Collection]:
        """获取所有收藏夹。先 resolve url_token，再加权请求收藏夹列表."""
        url_token = self._resolve_url_token()
        collections = []
        offset = 0
        limit = 20

        while True:
            r = self._request("GET", f"{BASE_URL}/people/{url_token}/collections",
                              params={"limit": limit, "offset": offset})
            if r.status_code != 200:
                raise RuntimeError(f"获取收藏夹列表失败: HTTP {r.status_code} {r.text[:200]}")

            data = r.json()
            for item in data.get("data", []):
                collections.append(Collection.from_api(item))

            paging = data.get("paging", {})
            if not paging.get("is_end", True):
                offset += limit
            else:
                break

            if len(collections) >= 1000:
                break

        return collections

    def get_collection_items(self, collection_id: int, max_items: int = 0) -> list[CollectionItem]:
        """获取收藏夹中的内容列表（不包含正文 HTML）。
        使用 /contents 端点（扁平数据结构，而非 /items 的嵌套 content 字段）。"""
        items = []
        offset = 0
        page_size = 20

        while True:
            r = self._request("GET", f"{BASE_URL}/collections/{collection_id}/contents",
                              params={"limit": page_size, "offset": offset})
            if r.status_code != 200:
                raise RuntimeError(f"获取收藏夹内容失败: HTTP {r.status_code} {r.text[:200]}")

            data = r.json()
            for item in data.get("data", []):
                items.append(CollectionItem.from_api(item))

            paging = data.get("paging", {})
            if not paging.get("is_end", True):
                offset += page_size
            else:
                break

            if max_items and len(items) >= max_items:
                break

        return items

    def fetch_answer_content(self, answer_id: int) -> Optional[str]:
        """获取回答的 HTML content."""
        r = self._request("GET", f"{BASE_URL}/answers/{answer_id}",
                          params={"include": "content"})
        if r.status_code == 200:
            return r.json().get("content", "")
        return None

    def fetch_article_content(self, article_id: int) -> Optional[str]:
        """获取文章的 HTML content (可能 403)."""
        r = self._request("GET", f"https://zhuanlan.zhihu.com/api/articles/{article_id}")
        if r.status_code == 200:
            return r.json().get("content", "")
        return None

    def fetch_article_html(self, article_id: int) -> Optional[str]:
        """降级：爬取专栏文章 HTML 页面."""
        from bs4 import BeautifulSoup

        r = self._request("GET", f"https://zhuanlan.zhihu.com/p/{article_id}")
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "lxml")
        # Try multiple content selectors
        for selector in [
            "div.Post-RichText",
            "div.RichText",
            "article",
            ".Post-content",
        ]:
            el = soup.select_one(selector)
            if el:
                return str(el)
        return None

    def fetch_answer_html(self, question_id: int, answer_id: int) -> Optional[str]:
        """降级：爬取回答 HTML 页面."""
        from bs4 import BeautifulSoup

        r = self._request("GET", f"https://www.zhihu.com/question/{question_id}/answer/{answer_id}")
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "lxml")
        for selector in [
            "div.RichText",
            "div.AnswerCard div.RichText",
            "div.ContentItem-RichText",
        ]:
            el = soup.select_one(selector)
            if el:
                return str(el)
        return None
