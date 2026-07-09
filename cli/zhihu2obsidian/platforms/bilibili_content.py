"""Bilibili subtitle and AI summary extraction."""

import hashlib
import time
import urllib.parse
from typing import Any

import requests

_BAPI_BASE = "https://api.bilibili.com"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}

WBI_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]


# ── WBI signing ───────────────────────────────────────

def _get_mixin_key(orig: str) -> str:
    buf: list[str] = []
    for i in WBI_MIXIN_KEY_ENC_TAB:
        buf.append(orig[i])
    return "".join(buf)[:32]


def _enc_wbi(params: dict, img_key: str, sub_key: str) -> dict:
    mixin_key = _get_mixin_key(img_key + sub_key)
    curr_time = round(time.time())
    params["wts"] = curr_time
    params = dict(sorted(params.items()))
    params = {
        k: "".join(ch for ch in str(v) if ch not in "!'()*")
        for k, v in params.items()
    }
    query = urllib.parse.urlencode(params)
    wbi_sign = hashlib.md5((query + mixin_key).encode()).hexdigest()
    params["w_rid"] = wbi_sign
    return params


def _get_wbi_keys(sessdata: str | None) -> tuple[str, str] | None:
    """Fetch WBI signing keys from nav API."""
    headers = dict(_HEADERS)
    if sessdata:
        headers["Cookie"] = f"SESSDATA={sessdata}"
    try:
        resp = requests.get(
            f"{_BAPI_BASE}/x/web-interface/nav", headers=headers, timeout=10
        )
        data = resp.json()["data"]["wbi_img"]
        img_key = data["img_url"].rsplit("/", 1)[1].split(".")[0]
        sub_key = data["sub_url"].rsplit("/", 1)[1].split(".")[0]
        return img_key, sub_key
    except Exception:
        return None


# ── Video info ────────────────────────────────────────

def get_video_info(
    bvid: str, sessdata: str | None = None
) -> dict[str, Any] | None:
    """Get aid + cid + title + desc."""
    headers = dict(_HEADERS)
    if sessdata:
        headers["Cookie"] = f"SESSDATA={sessdata}"
    try:
        resp = requests.get(
            f"{_BAPI_BASE}/x/web-interface/view?bvid={bvid}",
            headers=headers, timeout=10,
        )
        d = resp.json()
        if d.get("code") != 0:
            return None
        return d["data"]
    except Exception:
        return None


# ── Subtitle ──────────────────────────────────────────

def fetch_subtitle(
    bvid: str, aid: int, cid: int, sessdata: str | None = None
) -> list[dict] | None:
    """Fetch subtitle transcript from CDN.

    Returns list of ``{"from": float, "to": float, "content": str}``
    or ``None`` if unavailable.
    """
    headers = dict(_HEADERS)
    if sessdata:
        headers["Cookie"] = f"SESSDATA={sessdata}"
    try:
        resp = requests.get(
            f"{_BAPI_BASE}/x/player/wbi/v2?aid={aid}&cid={cid}",
            headers=headers, timeout=10,
        )
        subtitles = (
            resp.json()
            .get("data", {})
            .get("subtitle", {})
            .get("subtitles", [])
        )
        if not subtitles:
            return None

        # Prefer Chinese subtitle
        sub_url: str | None = None
        for sub in subtitles:
            if "zh" in sub.get("lan", "").lower():
                sub_url = sub["subtitle_url"]
                break
        if not sub_url:
            sub_url = subtitles[0].get("subtitle_url")

        if not sub_url:
            return None

        if sub_url.startswith("//"):
            sub_url = "https:" + sub_url

        sub_resp = requests.get(sub_url, headers=headers, timeout=15)
        return sub_resp.json().get("body", [])
    except Exception:
        return None


# ── AI summary ────────────────────────────────────────

def fetch_ai_summary(
    bvid: str, cid: int, sessdata: str | None = None
) -> dict | None:
    """Fetch AI video summary (summary paragraph + outline).

    Returns the ``model_result`` dict or ``None``.
    """
    headers = dict(_HEADERS)
    if sessdata:
        headers["Cookie"] = f"SESSDATA={sessdata}"

    keys = _get_wbi_keys(sessdata)
    if not keys:
        return None
    img_key, sub_key = keys

    params = _enc_wbi({"bvid": bvid, "cid": cid}, img_key, sub_key)
    try:
        resp = requests.get(
            f"{_BAPI_BASE}/x/web-interface/view/conclusion/get",
            params=params, headers=headers, timeout=10,
        )
        d = resp.json()
        if d.get("code") != 0:
            return None
        result = d.get("data", {}).get("model_result", {})
        if result.get("result_type", 0) == 0:
            return None
        return result
    except Exception:
        return None


# ── Formatting helpers ────────────────────────────────

def _fmt_ts(sec: float) -> str:
    """Format seconds to ``M:SS`` or ``H:MM:SS``."""
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_subtitle_md(body: list[dict]) -> str:
    """Format subtitle body as timestamped markdown lines."""
    if not body:
        return ""
    parts = []
    for item in body:
        ts = _fmt_ts(item.get("from", 0))
        parts.append(f"[{ts}] {item.get('content', '')}")
    return "\n".join(parts)


def format_summary_md(result: dict) -> str:
    """Format AI summary result as structured markdown sections.

    Returns sections for summary paragraph, outline, and AI subtitle.
    """
    sections: list[str] = []

    # ── Summary paragraph ──
    summary = (result.get("summary") or "").strip()
    if summary:
        sections.append("## AI 摘要\n")
        sections.append(summary)

    # ── Outline ──
    outline = result.get("outline") or []
    if outline:
        sections.append("")
        sections.append("## 内容大纲\n")
        for i, section in enumerate(outline, 1):
            title = section.get("title") or f"部分 {i}"
            ts_str = _fmt_ts(section.get("timestamp", 0))
            sections.append(f"### {i}. {title} ({ts_str})\n")
            for point in section.get("part_outline") or []:
                content = point.get("content", "")
                pt_ts = point.get("timestamp")
                if pt_ts:
                    sections.append(f"- [{_fmt_ts(pt_ts)}] {content}")
                else:
                    sections.append(f"- {content}")
            sections.append("")

    # ── AI subtitle ──
    subtitle = result.get("subtitle") or []
    if subtitle:
        lines: list[str] = []
        for section in subtitle:
            for item in section.get("part_subtitle") or []:
                content = item.get("content", "")
                if content:
                    lines.append(content)
        if lines:
            sections.append("## AI 字幕\n")
            sections.extend(lines)

    return "\n".join(sections).strip()


def build_video_md(
    bvid: str,
    sessdata: str | None = None,
) -> str:
    """Build rich markdown content for a Bilibili video.

    Priority: AI summary > CC subtitle > plain description.
    Returns markdown string.
    """
    info = get_video_info(bvid, sessdata)
    if not info:
        return ""

    desc = (info.get("desc") or "").strip()
    aid = info.get("aid", 0)
    cid = info.get("cid", 0)
    parts: list[str] = []

    # 1) AI summary (richest)
    ai_result = fetch_ai_summary(bvid, cid, sessdata) if cid else None
    if ai_result:
        summary_md = format_summary_md(ai_result)
        if summary_md:
            parts.append(summary_md)

    # 2) CC subtitle (full transcript)
    if cid:
        sub_body = fetch_subtitle(bvid, aid, cid, sessdata)
        if sub_body:
            sub_md = format_subtitle_md(sub_body)
            if sub_md:
                if parts:
                    parts.append("---\n")
                parts.append("## 字幕全文\n")
                parts.append(sub_md)

    # 3) Description (always available, always included)
    if desc:
        if parts:
            parts.append("---\n")
        parts.append("## 视频简介\n")
        parts.append(desc)

    return "\n".join(parts)
