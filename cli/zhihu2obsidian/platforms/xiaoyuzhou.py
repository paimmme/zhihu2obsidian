"""小宇宙播客 — 热门榜适配器 (零认证, xyzrank JSON API)."""

from __future__ import annotations

import datetime
import textwrap
from dataclasses import dataclass, field
from typing import Any

import requests

XYZRANK_BASE = "https://xyzrank.eddiehe.top"


@dataclass
class Episode:
    """单期播客."""

    title: str
    podcast_name: str
    podcast_id: str
    link: str
    play_count: int = 0
    comment_count: int = 0
    subscription: int = 0
    duration_min: int = 0
    post_time: str = ""
    genre: str = ""
    open_rate: float = 0.0
    total_episodes: int = 0
    last_release_days: float = 0.0

    @property
    def url(self) -> str:
        return self.link

    @property
    def duration_str(self) -> str:
        h, m = divmod(self.duration_min, 60)
        if h:
            return f"{h}h{m}m"
        return f"{m}m"

    @property
    def post_date(self) -> str:
        if not self.post_time:
            return "?"
        try:
            dt = datetime.datetime.fromisoformat(self.post_time.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return self.post_time[:10]


def fetch_hot_episodes() -> list[Episode]:
    """获取热门榜单 (约100条)."""
    resp = requests.get(f"{XYZRANK_BASE}/hot_episodes.json", timeout=15)
    data = resp.json()
    episodes_data = data.get("data", {}).get("episodes", [])
    return [_parse_ep(e) for e in episodes_data]


def fetch_full_rank() -> list[Episode]:
    """获取完整榜单 (播客排名)."""
    resp = requests.get(f"{XYZRANK_BASE}/full.json", timeout=15)
    data = resp.json()
    episodes_data = data.get("data", {}).get("episodes", [])
    return [_parse_ep(e) for e in episodes_data]


def _parse_ep(e: dict) -> Episode:
    return Episode(
        title=e.get("title", ""),
        podcast_name=e.get("podcastName", ""),
        podcast_id=e.get("podcastID", ""),
        link=e.get("link", ""),
        play_count=e.get("playCount", 0),
        comment_count=e.get("commentCount", 0),
        subscription=e.get("subscription", 0),
        duration_min=e.get("duration", 0),
        post_time=e.get("postTime", ""),
        genre=e.get("primaryGenreName", ""),
        open_rate=e.get("openRate", 0.0),
        total_episodes=e.get("totalEpisodesCount", 0),
        last_release_days=e.get("lastReleaseDateDayCount", 0.0),
    )


# ── 风格分析 ────────────────────────────────────────


@dataclass
class StyleProfile:
    """小宇宙平台风格画像."""

    title_patterns: list[str] = field(default_factory=list)
    title_avg_len: int = 0
    genres: list[tuple[str, int]] = field(default_factory=list)
    avg_duration_min: float = 0.0
    duration_distribution: list[tuple[str, int]] = field(default_factory=list)
    top_podcasts: list[tuple[str, int]] = field(default_factory=list)
    sample_titles: list[str] = field(default_factory=list)
    episode_count: int = 0


def analyze_style(episodes: list[Episode] | None = None) -> StyleProfile:
    """从热门榜数据提取小宇宙风格画像."""
    if episodes is None:
        episodes = fetch_hot_episodes()

    profile = StyleProfile(episode_count=len(episodes))

    # Title patterns
    prefixes = ["EP", "Vol", "E", "No", "#", "S"]
    patterns: list[str] = []
    for ep in episodes[:50]:
        t = ep.title
        for p in prefixes:
            if t.startswith(p) or t.startswith(p.lower()):
                patterns.append("编号前缀")
                break
        if "：" in t:
            patterns.append("冒号分隔")
        if "｜" in t:
            patterns.append("竖线分隔")
        if "|" in t:
            patterns.append("竖线分隔")
        if "对话" in t:
            patterns.append("对话/嘉宾")
        if "x" in t.lower() or "×" in t:
            patterns.append("多人对谈")
    from collections import Counter
    pattern_counts = Counter(patterns)
    profile.title_patterns = [f"{p}x{c}" for p, c in pattern_counts.most_common(6)]

    # Title length
    profile.title_avg_len = sum(len(e.title) for e in episodes) // len(episodes) if episodes else 0

    # Genre distribution
    genre_counts: Counter = Counter()
    for ep in episodes:
        if ep.genre:
            genre_counts[ep.genre] += 1
    profile.genres = genre_counts.most_common(10)

    # Duration
    durations = [e.duration_min for e in episodes if e.duration_min > 0]
    profile.avg_duration_min = round(sum(durations) / len(durations), 1) if durations else 0.0

    # Duration distribution
    buckets = {"<15m": 0, "15-30m": 0, "30-60m": 0, "60-90m": 0, "90-120m": 0, ">120m": 0}
    for d in durations:
        if d < 15:
            buckets["<15m"] += 1
        elif d < 30:
            buckets["15-30m"] += 1
        elif d < 60:
            buckets["30-60m"] += 1
        elif d < 90:
            buckets["60-90m"] += 1
        elif d < 120:
            buckets["90-120m"] += 1
        else:
            buckets[">120m"] += 1
    profile.duration_distribution = sorted(buckets.items(), key=lambda x: -x[1])

    # Top podcasts by play count
    podcast_plays: Counter = Counter()
    for ep in episodes:
        podcast_plays[ep.podcast_name] += ep.play_count
    profile.top_podcasts = podcast_plays.most_common(10)

    # Sample titles
    profile.sample_titles = [e.title[:50] for e in episodes[:8]]

    return profile


def format_style_report(profile: StyleProfile) -> str:
    """格式化为可读报告."""
    lines = [
        "📊 小宇宙热门榜风格分析",
        "═" * 40,
        "",
        f"分析样本: {profile.episode_count} 期热门播客",
        "",
        "📝 标题模式:",
    ]
    for p in profile.title_patterns:
        lines.append(f"   • {p}")
    lines.append(f"   平均标题长度: {profile.title_avg_len} 字")
    lines.append("")

    lines.append("📂 热门分类:")
    for genre, count in profile.genres:
        pct = count * 100 // profile.episode_count
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        lines.append(f"   {genre:<12s} {bar} {count}期 ({pct}%)")

    lines.append("")
    lines.append("⏱ 时长分布:")
    avg = profile.avg_duration_min
    lines.append(f"   平均 {avg} 分钟")
    for bucket, count in profile.duration_distribution:
        pct = count * 100 // profile.episode_count
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        lines.append(f"   {bucket:<10s} {bar} {count}期 ({pct}%)")

    lines.append("")
    lines.append("🏆 最热播客:")
    for name, plays in profile.top_podcasts[:5]:
        lines.append(f"   • {name:<16s} 总播放 {plays:,}")

    lines.append("")
    lines.append("💡 标题样例:")
    for t in profile.sample_titles:
        lines.append(f"   • {t}")

    return "\n".join(lines)


# ── 适配引擎 ────────────────────────────────────────


def generate_podcast_outline(
    content_texts: list[str],
    topic: str,
    style_profile: StyleProfile | None = None,
    use_llm: bool = False,
    api_key: str = "",
) -> str:
    """从知识库内容生成小宇宙风格播客大纲.

    无 API key 时使用规则模板, 有 key 时调用 DeepSeek 生成.
    """
    if use_llm and api_key:
        return _llm_outline(content_texts, topic, api_key)
    return _template_outline(content_texts, topic, style_profile or analyze_style())


def _template_outline(
    content_texts: list[str], topic: str, profile: StyleProfile
) -> str:
    """基于模板生成大纲."""
    avg_dur = profile.avg_duration_min
    avg_dur_str = f"{int(avg_dur)}分钟" if avg_dur else "60分钟"

    # Suggest title
    title_suggestions = [
        f"Vol.??? 和{topic}有关的那些事，一次聊透",
        f"EP??? 对话{topic}：从入门到实践，我们踩过的坑",
        f"#??? {topic}到底改变了什么？",
    ]

    sections = [
        f"🎙 播客大纲 — {topic}",
        "═" * 50,
        "",
        f"预计时长: {avg_dur_str}",
        "",
        "## 标题建议",
        *[f"   {i+1}. {s}" for i, s in enumerate(title_suggestions)],
        "",
        "## 开场 (5-8分钟)",
        "   引入话题: 为什么今天聊这个？",
        "   背景: 简短介绍话题背景",
        "   ⚡ 抛出核心问题",
        "",
        "## 主体 (40-50分钟)",
    ]

    # Add content from knowledge base
    for i, text in enumerate(content_texts[:5]):
        snippet = textwrap.shorten(text.strip(), width=120, placeholder="...")
        sections.append(f"   {i+1}. 📖 素材 {i+1}")
        sections.append(f"       {snippet}")
        sections.append(f"       讨论点: 这个概念为什么重要? 实际应用? 争议?")
        sections.append("")

    sections.extend([
        "## 深度讨论 (10-15分钟)",
        "   争议点: 这个领域的最大争议是什么？",
        "   不同观点: 支持 vs 反对",
        "   个人立场: 我们怎么看？",
        "",
        "## 观众互动 / 总结 (5-10分钟)",
        "   给听众的建议",
        "   推荐资源/延伸阅读",
        "   📢 下期预告",
        "",
        "---",
        "📝 制作笔记",
        "   本期素材来源: 知乎收藏夹 + Bilibili 收藏",
        f"   AI 生成大纲, {datetime.date.today().isoformat()}",
    ])

    return "\n".join(sections)


def _llm_outline(
    content_texts: list[str], topic: str, api_key: str
) -> str:
    """用 DeepSeek API 生成播客大纲."""
    import json as _json

    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是播客大纲策划师。根据用户提供的素材,生成小宇宙风格播客大纲。\n"
                            "小宇宙热门播客特征:\n"
                            "- 标题有编号前缀 (Vol/EP/No/#), 冒号/竖线分隔主副标题\n"
                            "- 时长60-90分钟为主\n"
                            "- 常见模式: 对话/嘉宾、多人对谈、热点解读\n"
                            "- 开场抛出问题, 主体层层递进, 结尾给建议\n"
                            "输出格式: Markdown, 含标题建议、开场、主体分段、深度讨论、总结"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"话题: {topic}\n\n"
                            f"素材:\n" + "\n---\n".join(
                                textwrap.shorten(t, width=300, placeholder="...")
                                for t in content_texts[:8]
                            )
                        ),
                    },
                ],
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            timeout=60,
        )
        result = resp.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ LLM 生成失败: {e}\n\n回退到模板大纲:\n\n{_template_outline(content_texts, topic, analyze_style())}"
