"""知识库 — 中文分块 (header-aware + 重叠窗口 + 最小尺寸)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

CHUNK_SIZE = 500
CHUNK_OVERLAP = 80
MIN_CHUNK = 80

HEADER_PATTERN = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


class Chunk:
    """知识库文本块."""

    def __init__(
        self,
        chunk_id: str,
        text: str,
        metadata: dict[str, Any],
        content_id: str = "",
        section_title: str = "",
        chunk_index: int = 0,
    ) -> None:
        self.chunk_id = chunk_id
        self.text = text
        self.metadata = metadata
        self.content_id = content_id
        self.section_title = section_title
        self.chunk_index = chunk_index
        self.content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter."""
    meta: dict[str, str] = {}
    if not text.startswith("---"):
        return meta, text
    end = text.find("---", 3)
    if end == -1:
        return meta, text
    for line in text[3:end].strip().split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, text[end + 3 :].strip()


def _split_by_headers(text: str) -> list[tuple[int, str, str]]:
    """Split markdown by h1/h2/h3.

    Returns [(level, section_title, content)].
    level: 1 for `#`, 2 for `##`, 3 for `###`.
    """
    sections: list[tuple[int, str, str]] = []
    prev_end = 0
    prev_level = 0
    prev_header = ""

    for m in HEADER_PATTERN.finditer(text):
        level = len(m.group(1))
        header = m.group(2).strip()

        if prev_header:
            body = text[prev_end : m.start()].strip()
            if body:
                sections.append((prev_level, prev_header, body))
            else:
                # empty section — skip, but use header as context for next
                sections.append((prev_level, prev_header, "(接上)"))
        else:
            # First header — text before it
            before = text[: m.start()].strip()
            if before:
                sections.append((0, "", before))

        prev_level = level
        prev_header = header
        prev_end = m.end()

    if prev_header:
        sections.append((prev_level, prev_header, text[prev_end:].strip()))
    else:
        sections.append((0, "", text.strip()))

    return sections


def _chunk_section(
    section_text: str,
    section_title: str,
    metadata: dict[str, str],
    content_id: str,
    start_idx: int,
) -> list[Chunk]:
    """Split a single section into chunks with overlap."""
    if len(section_text) < MIN_CHUNK:
        return []

    chunks: list[Chunk] = []
    chunk_size = CHUNK_SIZE

    if len(section_text) <= chunk_size:
        c = Chunk(
            chunk_id=f"{content_id}_s{start_idx:03d}" if content_id else f"s{start_idx:03d}",
            text=section_text,
            metadata=metadata,
            content_id=content_id,
            section_title=section_title,
            chunk_index=start_idx,
        )
        return [c]

    # Split by paragraph (double newline), then by sentence boundary
    paragraphs = re.split(r"\n\n+", section_text)
    buffer = ""
    idx = start_idx

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if not buffer:
            buffer = para
        elif len(buffer) + len(para) + 2 < chunk_size:
            buffer += "\n\n" + para
        else:
            # Flush buffer
            chunks.append(Chunk(
                chunk_id=f"{content_id}_s{idx:03d}" if content_id else f"s{idx:03d}",
                text=buffer.strip(),
                metadata=metadata,
                content_id=content_id,
                section_title=section_title,
                chunk_index=idx,
            ))
            idx += 1

            # Overlap: keep last paragraph-ish portion
            overlap_len = min(CHUNK_OVERLAP, len(buffer) // 2)
            # Try to break at sentence boundary
            overlap_text = buffer[-overlap_len:]
            sent_break = re.search(r"[。！？.!?]\s*", overlap_text)
            if sent_break:
                overlap_text = overlap_text[sent_break.end():]
            buffer = overlap_text + "\n\n" + para

    if buffer.strip() and len(buffer.strip()) >= MIN_CHUNK:
        chunks.append(Chunk(
            chunk_id=f"{content_id}_s{idx:03d}" if content_id else f"s{idx:03d}",
            text=buffer.strip(),
            metadata=metadata,
            content_id=content_id,
            section_title=section_title,
            chunk_index=idx,
        ))

    return chunks


def chunk_markdown_file(filepath: Path) -> list[Chunk]:
    """Split a markdown file into chunks."""
    text = filepath.read_text(encoding="utf-8")
    metadata, body = _parse_frontmatter(text)

    # Build content_id from metadata + file path
    content_id = metadata.get("content_id", filepath.stem)
    parent = filepath.parent.name
    if parent and parent not in (".", "") and parent not in content_id:
        content_id = f"{parent}__{content_id}"

    if not body:
        return []

    # Inject metadata into every chunk
    base_meta = dict(metadata)
    base_meta["source"] = str(filepath.relative_to(filepath.parent.parent) if filepath.parent.parent else filepath.name)

    chunks: list[Chunk] = []
    sections = _split_by_headers(body)
    idx = 0

    for level, section_title, section_text in sections:
        if level == 0:
            st = section_title  # text before first header
        else:
            st = section_title

        section_chunks = _chunk_section(
            section_text, st, base_meta, content_id, idx
        )
        chunks.extend(section_chunks)
        idx += len(section_chunks)

    return chunks


def chunk_all_markdowns(vault_dir: Path) -> list[Chunk]:
    """Chunk all .md files in vault directory."""
    chunks: list[Chunk] = []
    for fpath in sorted(vault_dir.rglob("*.md")):
        if ".state" in str(fpath) or fpath.name == "README.md":
            continue
        try:
            chunks.extend(chunk_markdown_file(fpath))
        except Exception as e:
            print(f"  ⚠ {fpath.name}: {e}")
    return chunks
