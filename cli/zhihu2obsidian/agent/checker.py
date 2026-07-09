"""写作质量检查 — 段落相似度 / 来源覆盖 / 依赖检测."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import requests

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"

# ── 阈值 ─────────────────────────────────────────
HIGH_SIM_THRESHOLD = 0.45  # 高相似（标红）
MOD_SIM_THRESHOLD = 0.30   # 中等相似（标黄）
MIN_PARAGRAPH_CHARS = 40   # 最小段落长度

REWRITE_PROMPT = """改写以下段落，保留核心观点但换一种表达方式。
目标是降低与原文的相似度，同时保持自然流畅的中文。

只返回改写后的段落，不要解释。"""


@dataclass
class ParagraphCheck:
    """单个段落检查结果."""

    index: int = 0
    text: str = ""
    max_score: float = 0.0
    source_title: str = ""
    source_content_id: str = ""
    source_author: str = ""
    source_platform: str = ""
    flagged: bool = False
    level: str = "good"  # good / moderate / high
    rewrite: str = ""


@dataclass
class WritingCheckReport:
    """完整质量检查报告."""

    draft_title: str = ""
    total_paragraphs: int = 0
    flagged_high: int = 0
    flagged_moderate: int = 0
    avg_score: float = 0.0
    paragraphs: list[ParagraphCheck] = field(default_factory=list)
    source_coverage: dict[str, int] = field(default_factory=dict)
    overreliance_source: str = ""
    overreliance_pct: float = 0.0
    overall_verdict: str = "good"  # good / needs_revision / high_risk


class WritingChecker:
    """写作质量检查器."""

    def __init__(
        self,
        retriever=None,
        api_key: str = "",
        model: str = DEFAULT_MODEL,
    ) -> None:
        self.retriever = retriever
        self.api_key = api_key
        self.model = model

    def check(self, draft: str, title: str = "") -> WritingCheckReport:
        """全流程：切段落 → 查相似 → 来源分析 → 报告."""
        paragraphs = self._split_paragraphs(draft)
        if not paragraphs:
            return WritingCheckReport(draft_title=title)

        checks: list[ParagraphCheck] = []
        source_usage: dict[str, int] = {}
        total_score = 0.0

        for i, para in enumerate(paragraphs):
            pc = self._check_paragraph(i, para)
            checks.append(pc)
            total_score += pc.max_score

            if pc.source_content_id:
                key = f"{pc.source_title} ({pc.source_author})" if pc.source_author else pc.source_title
                source_usage[key] = source_usage.get(key, 0) + 1

        # Overall stats
        flagged_high = sum(1 for c in checks if c.level == "high")
        flagged_mod = sum(1 for c in checks if c.level == "moderate")
        avg_score = total_score / len(checks) if checks else 0.0

        # Over-reliance check
        overreliance_source = ""
        overreliance_pct = 0.0
        total_refs = sum(source_usage.values())
        if total_refs > 0:
            top_source = max(source_usage, key=source_usage.get)
            top_count = source_usage[top_source]
            overreliance_pct = round(top_count / total_refs * 100)
            if overreliance_pct > 50:
                overreliance_source = top_source

        # Overall verdict
        if flagged_high > len(checks) * 0.3:
            verdict = "high_risk"
        elif flagged_high > 0 or overreliance_source:
            verdict = "needs_revision"
        else:
            verdict = "good"

        return WritingCheckReport(
            draft_title=title,
            total_paragraphs=len(paragraphs),
            flagged_high=flagged_high,
            flagged_moderate=flagged_mod,
            avg_score=round(avg_score, 3),
            paragraphs=checks,
            source_coverage=source_usage,
            overreliance_source=overreliance_source,
            overreliance_pct=overreliance_pct,
            overall_verdict=verdict,
        )

    # ── Private ───────────────────────────────────

    def _split_paragraphs(self, text: str) -> list[str]:
        """按双换行分割成段落，过滤太短的."""
        raw = re.split(r"\n\s*\n", text.strip())
        paragraphs = []
        for p in raw:
            p = p.strip()
            if len(p) < MIN_PARAGRAPH_CHARS:
                continue
            paragraphs.append(p)
        return paragraphs

    def _check_paragraph(self, idx: int, text: str) -> ParagraphCheck:
        """单个段落：检索相似度."""
        pc = ParagraphCheck(index=idx, text=text[:200])
        if not self.retriever:
            return pc

        try:
            results = self.retriever.embedder.search(text, n_results=3)
        except Exception:
            return pc

        if not results:
            return pc

        best = results[0]
        dist = best.get("distance", 0)
        score = round(1.0 - dist, 4)

        pc.max_score = score
        meta = best.get("metadata", {})
        pc.source_title = meta.get("title", "")
        pc.source_content_id = meta.get("content_id", "")
        pc.source_author = meta.get("author", "")
        pc.source_platform = meta.get("platform", "")

        if score >= HIGH_SIM_THRESHOLD:
            pc.level = "high"
            pc.flagged = True
        elif score >= MOD_SIM_THRESHOLD:
            pc.level = "moderate"
        else:
            pc.level = "good"

        return pc

    def _generate_rewrite(self, paragraphs: list[ParagraphCheck]) -> None:
        """逐个生成改写建议（更可靠的按段调用）."""
        flagged = [p for p in paragraphs if p.flagged]
        if not flagged or not self.api_key:
            return

        para_prompt = """改写以下段落，保留核心观点但换一种表达方式。
目标是降低与原文的相似度，同时保持自然流畅的中文。
只返回改写后的文本，不要解释，不要加引号。"""

        for p in flagged:
            try:
                resp = requests.post(
                    DEEPSEEK_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": REWRITE_PROMPT},
                            {"role": "user", "content": f"段落：\n{p.text}"},
                        ],
                        "temperature": 0.5,
                        "max_tokens": 500,
                        "stream": False,
                    },
                    timeout=30,
                )
            except requests.RequestException:
                continue

            if resp.status_code != 200:
                continue

            try:
                data = resp.json()
                p.rewrite = data["choices"][0]["message"]["content"].strip()
            except Exception:
                pass

    def render_report(self, report: WritingCheckReport) -> str:
        """渲染检查报告为可读文本."""
        title = report.draft_title or "(无标题)"
        lines = [f"# 写作质量检查: {title}", ""]

        # Verdict
        verdict_map = {
            "good": "✅ 原创度良好",
            "needs_revision": "⚠️ 需修改部分段落",
            "high_risk": "❌ 高风险 — 多处与原文高度相似",
        }
        lines.append(f"**总体评价: {verdict_map.get(report.overall_verdict, '?')}**")
        lines.append("")

        # Summary stats
        lines.append(f"- 总段落: {report.total_paragraphs}")
        lines.append(f"- 高相似: {report.flagged_high} 段 (>{HIGH_SIM_THRESHOLD})")
        lines.append(f"- 中等:   {report.flagged_moderate} 段 (>={MOD_SIM_THRESHOLD})")
        lines.append(f"- 平均相似度: {report.avg_score}")
        lines.append("")

        if report.overreliance_source:
            lines.append(f"⚠️ 过度依赖单一来源: {report.overreliance_source} ({report.overreliance_pct}%)")
            lines.append("")

        # Per-paragraph
        lines.append("---")
        lines.append("## 逐段落检查")
        lines.append("")

        for pc in report.paragraphs:
            level_label = {"high": "🔴 高相似", "moderate": "🟡 参考", "good": "🟢 原创"}
            label = level_label.get(pc.level, "❓")
            src = ""
            if pc.source_title:
                src = f" (匹配: {pc.source_title})"
            lines.append(f"  **{pc.index+1}. [{label}] 相似度: {pc.max_score:.3f}{src}**")
            lines.append(f"  > {pc.text}")
            if pc.rewrite:
                lines.append(f"  ✏️ 建议改写: {pc.rewrite}")
            lines.append("")

        # Source coverage
        if report.source_coverage:
            lines.append("---")
            lines.append("## 📚 素材使用分布")
            lines.append("")
            for src, count in sorted(report.source_coverage.items(), key=lambda x: -x[1]):
                bar = "█" * min(count, 20)
                lines.append(f"  {bar} {count}×  {src}")
            lines.append("")

        return "\n".join(lines)


# ── CLI-friendly ─────────────────────────────────

def check_text(
    text: str,
    title: str = "",
    retriever=None,
    api_key: str = "",
    model: str = DEFAULT_MODEL,
    with_rewrite: bool = False,
) -> WritingCheckReport:
    """快捷函数：传文本，返回报告."""
    checker = WritingChecker(retriever=retriever, api_key=api_key, model=model)
    report = checker.check(text, title=title)
    if with_rewrite and report.flagged_high > 0:
        checker._generate_rewrite(report.paragraphs)
    return report
