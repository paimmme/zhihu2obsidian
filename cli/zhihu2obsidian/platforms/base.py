"""平台适配器基类."""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PlatformCollection:
    """平台收藏夹."""
    id: str
    title: str
    item_count: int = 0
    description: str = ""
    updated_time: int = 0  # UNIX timestamp
    platform: str = ""


@dataclass
class PlatformItem:
    """平台收藏内容."""
    id: str  # platform-specific unique ID
    type: str  # video / article / image / etc.
    title: str = ""
    url: str = ""
    author_name: str = ""
    author_url: str = ""
    description: str = ""
    collect_time: int = 0  # UNIX timestamp when user bookmarked
    updated_time: int = 0  # UNIX timestamp of content update
    content_html: str = ""  # fetched content (HTML or plain text)
    tags: list[str] = field(default_factory=list)
    platform: str = ""
    extra: dict = field(default_factory=dict)  # platform-specific metadata

    @property
    def content_id(self) -> str:
        return f"{self.platform}_{self.id}"


class CookieJarBase:
    """Cookie 文件管理基类."""

    def __init__(self, cookie_file: str):
        self.cookie_file = Path(cookie_file)

    @classmethod
    def from_input(cls, cookie_file: str) -> "CookieJarBase":
        """交互式输入 cookie 对."""
        import getpass

        print(f"请输入 {cookie_file} 的 Cookie（Key=Value 格式，每行一个）")
        cookies = {}
        while True:
            line = getpass.getpass("  Cookie (空行结束): ").strip()
            if not line:
                break
            if "=" in line:
                k, v = line.split("=", 1)
                cookies[k.strip()] = v.strip()
            else:
                print("  格式错误: 需要 Key=Value")

        if not cookies:
            raise ValueError("至少需要一个 Cookie")

        cookie_path = Path(cookie_file)
        cookie_path.parent.mkdir(parents=True, exist_ok=True)
        cookie_path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
        print(f"✅ Cookie 已保存: {cookie_path}")
        return cls(cookie_file)

    def load_cookies(self) -> dict[str, str]:
        """加载 cookie 文件."""
        if not self.cookie_file.exists():
            return {}
        try:
            data = json.loads(self.cookie_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, cookie_file: str | None = None) -> None:
        ...


class Platform(ABC):
    """平台适配器基类。各平台实现此接口。"""

    def __init__(self, config, cookie_file: str):
        self.config = config
        self.cookie_file = cookie_file
        self._cookies: dict[str, str] = {}

    @property
    @abstractmethod
    def name(self) -> str:
        """平台名称."""
        ...

    @property
    def cookies(self) -> dict[str, str]:
        if not self._cookies:
            self._cookies = self._load_cookies()
        return self._cookies

    def _load_cookies(self) -> dict[str, str]:
        if not self.cookie_file or not os.path.exists(self.cookie_file):
            return {}
        try:
            with open(self.cookie_file, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    @abstractmethod
    def check_auth(self) -> tuple[bool, str]:
        """检查认证状态。返回 (ok, message)."""
        ...

    @abstractmethod
    def list_collections(self) -> list[PlatformCollection]:
        """列出收藏夹."""
        ...

    @abstractmethod
    def get_items(self, collection: PlatformCollection) -> list[PlatformItem]:
        """获取收藏夹内内容列表."""
        ...

    @abstractmethod
    def get_content(self, item: PlatformItem) -> str | None:
        """获取单条内容的 HTML."""
        ...
