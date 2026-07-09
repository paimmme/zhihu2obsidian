"""素材卡片 — LLM 驱动的结构化内容抽取."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"

ZHIHU_CARD_PROMPT = """你是一个写作素材分析师。分析以下知乎内容，提取可复用的写作素材。

返回格式：只返回 JSON，不要其他内容。

JSON 字段说明：
- core_points: 核心观点列表（2-5个，作者真正想表达的核心主张）
- arguments: 论据列表，每个对象包含 point（观点）、evidence（论据/证据）、type（类型：数据/案例/逻辑推理/引用）
- case_stories: 案例或故事列表
- key_quotes: 适合直接引用的金句列表
- counterpoints: 反方观点或可反驳的角度
- writing_angles: 基于此素材可以写的文章方向
- risk_notes: 内容中可能片面、过时或有争议的部分
- topics: 关联话题标签（3-8个）

注意：提取的是作者的观点和论据，不是总结全文。区分作者原创观点和引用的外部来源。"""

BILIBILI_CARD_PROMPT = """你是一个内容分析师。分析以下B站视频内容，提取可用的素材信息。

返回格式：只返回 JSON，不要其他内容。

JSON 字段说明：
- topic: 核心主题/问题
- key_points: 主要观点和论述列表
- examples: 案例或举例列表
- data_points: 可引用的数据或事实列表
- topics: 关联话题标签（3-5个）"""


@dataclass
class MaterialCard:
    """结构化素材卡片."""

    content_id: str = ""
    title: str = ""
    url: str = ""
    author: str = ""
    platform: str = "zhihu"
    card_type: str = "full"  # full / light

    # Core analysis (zhihu - full)
    core_points: list[str] = field(default_factory=list)
    arguments: list[dict] = field(default_factory=list)
    case_stories: list[str] = field(default_factory=list)
    key_quotes: list[str] = field(default_factory=list)
    counterpoints: list[str] = field(default_factory=list)
    writing_angles: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)

    # Topic analysis (bilibili - light)
    topic: str = ""
    key_points: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    data_points: list[str] = field(default_factory=list)

    # Cross-reference
    topics: list[str] = field(default_factory=list)
    related_content_ids: list[str] = field(default_factory=list)

    # Metadata
    extracted_at: str = ""
    content_hash: str = ""


class CardExtractor:
    """LLM 驱动的素材卡片抽取器.
    
    每篇内容抽取一张结构化素材卡片，包含核心观点、论据、案例、金句等。
    知乎 => 完整卡片 (full)，B站 => 轻量卡片 (light)。
    增量：仅处理文件内容哈希变化的文件。
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        knowledge_dir: Path | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.cards_dir = (
            (knowledge_dir / "cards") if knowledge_dir else Path(".knowledge/cards")
        )
        self.cards_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_file = self.cards_dir / "manifest.json"
        self._manifest: dict = self._load_manifest()

    # ── 文件哈希 / manifest ──────────────────────────

    def _file_hash(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

    def _load_manifest(self) -> dict:
        if self.manifest_file.exists():
            try:
                return json.loads(self.manifest_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_manifest(self) -> None:
        self.manifest_file.write_text(
            json.dumps(self._manifest, ensure_ascii=False, indent=2)
        )

    # ── 变更检测 ────────────────────────────────────

    def get_changed_files(self, vault_dir: Path) -> list[Path]:
        """返回内容哈希已变或新增的文件（需重新抽取）。"""
        known = dict(self._manifest.get("files", {}))
        changed: list[Path] = []
        for fpath in sorted(vault_dir.rglob("*.md")):
            if ".state" in str(fpath) or fpath.name == "README.md":
                continue
            rel = str(fpath.relative_to(vault_dir))
            fhash = self._file_hash(fpath)
            entry = known.get(rel)
            if entry and entry.get("hash") == fhash:
                continue  # 未变
            changed.append(fpath)
        return changed

    def clean_orphaned(self, vault_dir: Path) -> int:
        """清理已删除文件对应的卡片."""
        known = dict(self._manifest.get("files", {}))
        removed = 0
        for rel in list(known.keys()):
            fpath = vault_dir / rel
            if not fpath.exists():
                cid = known[rel].get("content_id", "")
                cf = self.cards_dir / f"{cid}.json"
                if cf.exists():
                    cf.unlink()
                self._manifest.get("files", {}).pop(rel, None)
                removed += 1
        if removed:
            self._save_manifest()
        return removed

    # ── 单篇抽取 ────────────────────────────────────

    def extract_card(self, filepath: Path, vault_dir: Path) -> MaterialCard | None:
        """抽取单篇内容的素材卡片."""
        from .chunker import _parse_frontmatter

        text = filepath.read_text(encoding="utf-8")
        metadata, body = _parse_frontmatter(text)
        if not body:
            return None

        platform = metadata.get("platform", "zhihu")
        content_id = metadata.get("content_id", filepath.stem)
        title = metadata.get("title", filepath.stem)
        url = metadata.get("url", "")
        author = metadata.get("author", "")
        content_hash = self._file_hash(filepath)
        card_type = "light" if platform == "bilibili" else "full"

        # 截断超长内容
        max_chars = 3000
        truncated = body[:max_chars]
        if len(body) > max_chars:
            truncated += "\n\n[内容已截断 — 共 {len(body)} 字符]"

        system_prompt = BILIBILI_CARD_PROMPT if platform == "bilibili" else ZHIHU_CARD_PROMPT
        user_prompt = f"## 标题\n{title}\n\n## 作者\n{author}\n\n## 正文\n{truncated}"

        result_text = self._call_llm(system_prompt, user_prompt)
        if not result_text:
            return None

        card_data = self._parse_llm_output(result_text)
        if not card_data:
            return None

        card = MaterialCard(
            content_id=content_id,
            title=title,
            url=url,
            author=author,
            platform=platform,
            card_type=card_type,
            core_points=card_data.get("core_points", []),
            arguments=card_data.get("arguments", []),
            case_stories=card_data.get("case_stories", []),
            key_quotes=card_data.get("key_quotes", []),
            counterpoints=card_data.get("counterpoints", []),
            writing_angles=card_data.get("writing_angles", []),
            risk_notes=card_data.get("risk_notes", []),
            topic=card_data.get("topic", ""),
            key_points=card_data.get("key_points", []),
            examples=card_data.get("examples", []),
            data_points=card_data.get("data_points", []),
            topics=card_data.get("topics", []),
            extracted_at=datetime.now().isoformat(),
            content_hash=content_hash,
        )

        self._save_card(card)
        self._update_manifest(filepath, vault_dir, content_hash, card_type, content_id)
        return card

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str | None:
        """调用 DeepSeek API."""
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
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2048,
                    "stream": False,
                },
                timeout=60,
            )
        except requests.RequestException as e:
            print(f"  ⚠ API 请求失败: {e}")
            return None

        if resp.status_code != 200:
            print(f"  ⚠ API 错误: HTTP {resp.status_code} {resp.text[:200]}")
            return None

        try:
            return resp.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError):
            return None

    @staticmethod
    def _parse_llm_output(text: str) -> dict | None:
        """从 LLM 回复中提取 JSON."""
        # 去除可能的 markdown 代码块包裹
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def _save_card(self, card: MaterialCard) -> None:
        card_file = self.cards_dir / f"{card.content_id}.json"
        card_file.write_text(
            json.dumps(asdict(card), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def _update_manifest(
        self, filepath: Path, vault_dir: Path, fhash: str, card_type: str, content_id: str
    ) -> None:
        rel = str(filepath.relative_to(vault_dir))
        self._manifest.setdefault("files", {})[rel] = {
            "hash": fhash,
            "type": card_type,
            "content_id": content_id,
        }
        self._save_manifest()

    # ── 查询 ────────────────────────────────────────

    def stats(self) -> dict:
        files = self._manifest.get("files", {})
        return {
            "total_cards": len(files),
            "full_cards": sum(1 for f in files.values() if f.get("type") == "full"),
            "light_cards": sum(1 for f in files.values() if f.get("type") == "light"),
            "cards_dir": str(self.cards_dir),
        }

    def get_card(self, content_id: str) -> MaterialCard | None:
        cf = self.cards_dir / f"{content_id}.json"
        if cf.exists():
            try:
                return MaterialCard(**json.loads(cf.read_text()))
            except Exception:
                return None
        return None

    def search(self, query: str, top_n: int = 5) -> list[MaterialCard]:
        """简单关键词搜索卡片（按 topics/core_points 匹配）。"""
        q = query.lower()
        scored: list[tuple[MaterialCard, int]] = []
        for f in self.cards_dir.glob("*.json"):
            if f.name == "manifest.json":
                continue
            try:
                card = MaterialCard(**json.loads(f.read_text()))
            except Exception:
                continue
            score = 0
            # topics 匹配权重最高
            for t in card.topics:
                if q in t.lower():
                    score += 3
            # core_points / key_points
            for cp in card.core_points + card.key_points:
                if q in cp.lower():
                    score += 2
            # case_stories / examples (may be str or dict from LLM)
            raw_stories = []
            for item in card.case_stories + card.examples:
                if isinstance(item, str):
                    raw_stories.append(item)
                elif isinstance(item, dict):
                    raw_stories.append(item.get("content", item.get("title", str(item))))
            for s in raw_stories:
                if q in s.lower():
                    score += 1
            for arg in card.arguments:
                for field in ("point", "evidence"):
                    if q in str(arg.get(field, "")).lower():
                        score += 1
                        break
            if score:
                scored.append((card, score))
        scored.sort(key=lambda x: -x[1])
        return [c for c, _ in scored[:top_n]]

    # ── 全量重置 ────────────────────────────────────

    def reset(self) -> None:
        """清空所有卡片和 manifest."""
        for f in self.cards_dir.glob("*.json"):
            if f.name == "manifest.json":
                continue
            f.unlink()
        self._manifest = {}
        self._save_manifest()
