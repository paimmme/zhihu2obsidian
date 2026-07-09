"""图片下载器 — 下载到 assets 目录，按 hash 去重."""

from __future__ import annotations

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from .models import ImageRef

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www.zhihu.com/",
}


def download_one(img: ImageRef, assets_dir: Path, session: requests.Session) -> tuple[str, bool]:
    """下载单张图片。返回 (url, success)."""
    filepath = assets_dir / img.content_id / img.filename
    if filepath.exists():
        return img.url, True  # 已存在

    filepath.parent.mkdir(parents=True, exist_ok=True)

    try:
        r = session.get(img.url, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            filepath.write_bytes(r.content)
            return img.url, True
        else:
            return img.url, False
    except requests.RequestException:
        return img.url, False


def download_all(images: list[ImageRef], assets_dir: Path, max_workers: int = 3) -> list[tuple[str, bool]]:
    """并发下载图片。返回 [(url, success), ...]"""
    if not images:
        return []

    results = []
    session = requests.Session()
    session.headers.update(HEADERS)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_one, img, assets_dir, session): img for img in images}
        for future in as_completed(futures):
            url, ok = future.result()
            results.append((url, ok))

    session.close()
    return results
