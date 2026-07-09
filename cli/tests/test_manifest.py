"""P3: Manifest CRUD 测试 (Embedder 空运行)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from zhihu2obsidian.knowledge.chunker import Chunk
from zhihu2obsidian.knowledge.embedder import Embedder


def _make_chunk(text: str, idx: int, content_id: str = "test_001") -> Chunk:
    return Chunk(
        chunk_id=f"{content_id}_s{idx:03d}",
        text=text,
        metadata={"source": "test.md", "platform": "zhihu"},
        content_id=content_id,
        section_title="",
        chunk_index=idx,
    )


def test_manifest_add_remove_cycle() -> None:
    """验证 add -> remove -> add 的 manifest 一致性."""
    with tempfile.TemporaryDirectory() as tmp:
        embedder = Embedder(Path(tmp))

        # Add chunks
        chunks = [_make_chunk("hello world", 0), _make_chunk("foo bar", 1)]
        n = embedder.add_chunks(chunks, rel_path="test.md")
        assert n == 2

        # Manifest should track them
        mf = json.loads((Path(tmp) / "manifest.json").read_text())
        files = mf.get("files", {})
        assert "test.md" in files
        assert len(files["test.md"]["chunk_ids"]) == 2

        # Remove by content_id
        removed = embedder.remove_by_content_id("test_001")
        assert removed == 2

        # Manifest should be clean or have empty file entry
        mf2 = json.loads((Path(tmp) / "manifest.json").read_text())
        assert "test.md" not in mf2.get("files", {})

        # Re-add
        chunks2 = [_make_chunk("hello world updated", 0, "test_001")]
        n2 = embedder.add_chunks(chunks2, rel_path="test.md")
        assert n2 == 1


def test_manifest_dedup() -> None:
    """验证内容哈希去重."""
    with tempfile.TemporaryDirectory() as tmp:
        embedder = Embedder(Path(tmp))
        c1 = _make_chunk("same text", 0, "test_002")
        c2 = _make_chunk("same text", 1, "test_002")  # same hash!
        n = embedder.add_chunks([c1, c2], rel_path="test.md")
        assert n == 1, "重复 chunk 应去重"


def test_manifest_incremental_add() -> None:
    """验证增量添加后 chunk 计数."""
    with tempfile.TemporaryDirectory() as tmp:
        embedder = Embedder(Path(tmp))
        # First batch
        chunks1 = [_make_chunk("first batch chunk A", 0, "inc_001")]
        assert embedder.add_chunks(chunks1, rel_path="a.md") == 1

        # Second batch (new file)
        chunks2 = [_make_chunk("second batch chunk B", 0, "inc_002")]
        assert embedder.add_chunks(chunks2, rel_path="b.md") == 1

        # Verify both files tracked
        mf = json.loads((Path(tmp) / "manifest.json").read_text())
        assert "a.md" in mf["files"]
        assert "b.md" in mf["files"]
