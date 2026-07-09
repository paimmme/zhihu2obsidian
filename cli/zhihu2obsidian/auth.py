"""Cookie 管理 — 读取/验证/导入."""

from __future__ import annotations

import json
from pathlib import Path

import requests

COOKIE_KEYS = {"d_c0", "z_c0"}


class CookieJar:
    """管理知乎 Cookie."""

    def __init__(self, cookies: dict[str, str]) -> None:
        self.cookies = cookies

    @classmethod
    def from_file(cls, path: Path) -> CookieJar:
        """从 JSON 文件读取 Cookie."""
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Cookie 文件格式错误：需要 JSON 对象")
        missing = COOKIE_KEYS - set(data.keys())
        if missing:
            raise ValueError(f"Cookie 文件缺少 key：{', '.join(sorted(missing))}")
        return cls(data)

    @classmethod
    def from_input(cls) -> CookieJar:
        """交互式输入 Cookie."""
        import getpass

        print("请输入知乎 Cookie（从浏览器 DevTools → Network → 复制为 cURL → 提取）")
        cookies = {}
        for key in sorted(COOKIE_KEYS):
            val = getpass.getpass(f"  {key}: ").strip()
            if val:
                cookies[key] = val
        missing = COOKIE_KEYS - set(cookies.keys())
        if missing:
            raise ValueError(f"缺少必要 key：{', '.join(sorted(missing))}")
        return cls(cookies)

    def to_dict(self) -> dict[str, str]:
        return dict(self.cookies)

    def check_valid(self) -> tuple[bool, str]:
        """测试 Cookie 是否有效 — 调用列表 API 探测."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://www.zhihu.com/",
            "Accept": "application/json, text/plain, */*",
        }
        try:
            r = requests.get(
                "https://www.zhihu.com/api/v4/me",
                cookies=self.cookies,
                headers=headers,
                timeout=15,
            )
            if r.status_code == 200:
                uid = r.json().get("url_token", "")
                return True, f"Cookie 有效 (用户: {r.json().get('name', uid)})"
            elif r.status_code == 401:
                return False, "Cookie 已过期或无效（401）"
            else:
                return False, f"响应异常: HTTP {r.status_code}"
        except requests.RequestException as e:
            return False, f"网络错误: {e}"
