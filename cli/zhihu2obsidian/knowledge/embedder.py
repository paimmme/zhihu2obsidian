"""向量存储 — ChromaDB 封装 (去重 + 增量更新)."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import chromadb

from .chunker import Chunk


class Embedder:
    """ChromaDB 向量存储 + 增量更新."""

    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self._client: chromadb.PersistentClient | None = None
        self._collection = None
        self._ef = None
        self._manifest_file = storage_dir / "manifest.json"
        self._manifest: dict[str, Any] = self._load_manifest()

    # ── Client / Collection ──────────────────────────

    @property
    def client(self):
        if self._client is None:
            self._client = chromadb.PersistentClient(path=str(self.storage_dir))
        return self._client

    @property
    def collection(self):
        if self._collection is None:
            try:
                self._collection = self.client.get_collection("zhihu_knowledge")
            except (ValueError, chromadb.errors.NotFoundError):
                self._collection = self._create_collection()
        return self._collection

    def _create_collection(self):
        return self.client.create_collection(
            name="zhihu_knowledge",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._get_embedding_function(),
        )

    @staticmethod
    def _get_embedding_function():
        """ONNX all-MiniLM-L6-v2 (已缓存, 无网络). 移除 BGE 尝试 — HF 被墙."""
        try:
            from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
            ef = DefaultEmbeddingFunction()
            ef(["test"])
            return ef
        except Exception:
            return None

    # ── Manifest (增量追踪) ──────────────────────────

    def _load_manifest(self) -> dict:
        if self._manifest_file.exists():
            try:
                return json.loads(self._manifest_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_manifest(self) -> None:
        self._manifest_file.parent.mkdir(parents=True, exist_ok=True)
        self._manifest_file.write_text(
            json.dumps(self._manifest, ensure_ascii=False, indent=2)
        )

    def _file_hash(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

    def get_changed_files(self, vault_dir: Path) -> tuple[list[Path], list[str]]:
        """Check which .md files need re-chunking.

        Returns (changed_files, removed_file_ids).
        """
        known = dict(self._manifest.get("files", {}))
        current_files: dict[str, Path] = {}
        changed: list[Path] = []
        removed: list[str] = []

        for fpath in sorted(vault_dir.rglob("*.md")):
            if ".state" in str(fpath) or fpath.name == "README.md":
                continue
            rel = str(fpath.relative_to(vault_dir))
            current_files[rel] = fpath
            fhash = self._file_hash(fpath)
            entry = known.get(rel)
            if entry and entry.get("hash") == fhash:
                continue  # unchanged
            changed.append(fpath)

        # Files that no longer exist
        for rel in known:
            if rel not in current_files:
                removed.append(rel)

        return changed, removed

    def remove_file_chunks(self, rel_path: str) -> None:
        """Remove all chunks associated with a file."""
        entry = self._manifest.get("files", {}).get(rel_path)
        if not entry:
            return
        chunk_ids = entry.get("chunk_ids", [])
        if chunk_ids:
            try:
                self.collection.delete(ids=chunk_ids)
            except Exception:
                pass
        self._manifest.get("files", {}).pop(rel_path, None)
        self._save_manifest()

    def remove_by_content_id(self, content_id: str) -> int:
        """Force-delete all chunks by content_id from ChromaDB.
        
        Also removes matching hashes from manifest so dedup doesn't block
        re-adding the same chunks with updated metadata.
        Works even when manifest per-file chunk_ids are incomplete.
        Also removes per-file manifest entries whose chunk_ids are fully
        consumed by this deletion.
        Returns count of deleted chunks.
        """
        hashes_to_remove: list[str] = []
        deleted_ids: list[str] = []
        try:
            results = self.collection.get(where={"content_id": content_id})
            if results and results.get("ids"):
                deleted_ids = list(results["ids"])
                if results.get("metadatas"):
                    for m in results["metadatas"]:
                        h = m.get("content_hash", "")
                        if h:
                            hashes_to_remove.append(h)
                self.collection.delete(ids=deleted_ids)
        except Exception:
            pass
        
        # Remove hashes from manifest so re-add works
        if hashes_to_remove:
            hf = set(self._manifest.get("_chunk_hashes", []))
            hf.difference_update(hashes_to_remove)
            self._manifest["_chunk_hashes"] = list(hf)
            # Also scrub from per-file entries
            for entry in self._manifest.get("files", {}).values():
                entry_hashes = entry.get("hashes", [])
                entry["hashes"] = [h for h in entry_hashes if h not in hashes_to_remove]
                if deleted_ids:
                    entry["chunk_ids"] = [
                        cid for cid in entry.get("chunk_ids", [])
                        if cid not in deleted_ids
                    ]
        
        # Remove per-file entries that are now empty (all chunks deleted)
        if deleted_ids:
            files_dict = self._manifest.get("files", {})
            stale_rels = [
                rel for rel, entry in files_dict.items()
                if not entry.get("chunk_ids", [])
            ]
            for rel in stale_rels:
                del files_dict[rel]
        
        self._save_manifest()
        return len(deleted_ids)

    def add_chunks(self, chunks: list[Chunk], rel_path: str = "") -> int:
        """Add chunks, skipping content hashes that already exist.

        Returns count of new chunks added.
        """
        if not chunks:
            return 0

        # Dedup by content hash within current batch
        known_hashes: set[str] = set()
        # Global chunk hashes (used when rel_path is not tracked per-file)
        known_hashes.update(self._manifest.get("_chunk_hashes", []))
        # Per-file chunk hashes
        for entry in self._manifest.get("files", {}).values():
            known_hashes.update(entry.get("hashes", []))

        new_chunks: list[Chunk] = []
        new_ids: list[str] = []
        new_hashes: list[str] = []

        for c in chunks:
            if c.content_hash in known_hashes:
                continue
            known_hashes.add(c.content_hash)
            new_chunks.append(c)
            new_ids.append(c.chunk_id)
            new_hashes.append(c.content_hash)

        if not new_chunks:
            return 0

        # Batch add
        batch_size = 100
        total = 0
        for i in range(0, len(new_chunks), batch_size):
            batch = new_chunks[i : i + batch_size]
            self.collection.add(
                ids=[c.chunk_id for c in batch],
                documents=[c.text for c in batch],
                metadatas=[
                    {
                        "content_id": c.content_id,
                        "section": c.section_title,
                        "chunk_index": c.chunk_index,
                        "content_hash": c.content_hash,
                        "source": c.metadata.get("source", ""),
                        "platform": c.metadata.get("platform", ""),
                        "type": c.metadata.get("type", ""),
                        "author": c.metadata.get("author", ""),
                        "title": c.metadata.get("title", ""),
                        "collection": c.metadata.get("collection", ""),
                    }
                    for c in batch
                ],
            )
            total += len(batch)

        # Update manifest
        if rel_path:
            files = self._manifest.setdefault("files", {})
            if rel_path not in files:
                files[rel_path] = {"hash": "", "chunk_ids": [], "hashes": []}
            files[rel_path]["chunk_ids"].extend(new_ids)
            files[rel_path]["hashes"].extend(new_hashes)
        else:
            # Store globally when no per-file path available
            existing = self._manifest.setdefault("_chunk_hashes", [])
            existing.extend(new_hashes)
        self._save_manifest()

        return total

    def update_file_hashes(self, vault_dir: Path, changed_files: list[Path]) -> None:
        """Update manifest hashes after successful chunking."""
        files = self._manifest.setdefault("files", {})
        for fpath in changed_files:
            rel = str(fpath.relative_to(vault_dir))
            files[rel] = files.get(rel, {})
            files[rel]["hash"] = self._file_hash(fpath)
        self._save_manifest()

    # ── Query ────────────────────────────────────────

    def get_all(
        self, limit: int = 99999, offset: int = 0
    ) -> list[dict]:
        """Get all chunks (for wordcloud / stats)."""
        try:
            results = self.collection.get(limit=limit, offset=offset)
            items = []
            for i in range(len(results["ids"])):
                items.append({
                    "id": results["ids"][i],
                    "document": results["documents"][i] if results["documents"] else "",
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                })
            return items
        except Exception:
            return []

    def search(
        self, query: str, n_results: int = 5, filter_metadata: dict | None = None
    ) -> list[dict]:
        kwargs = {"n_results": n_results}
        if filter_metadata:
            kwargs["where"] = filter_metadata

        results = self.collection.query(query_texts=[query], **kwargs)

        items = []
        for i in range(len(results["ids"][0])):
            dist = results["distances"][0][i] if results["distances"] else 0
            items.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i] if results["documents"] else "",
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": dist,
                "score": round(1.0 - dist, 4),
            })
        return items

    # ── Stats ────────────────────────────────────────

    def count(self) -> int:
        return self.collection.count()

    def stats(self) -> dict:
        return {
            "total_chunks": self.count(),
            "tracked_files": len(self._manifest.get("files", {})),
            "storage_path": str(self.storage_dir),
        }

    # ── Full rebuild ──────────────────────────────────

    def delete_collection(self) -> None:
        try:
            self.client.delete_collection("zhihu_knowledge")
        except (ValueError, chromadb.errors.NotFoundError):
            pass
        self._collection = None
        self._manifest = {}
        self._save_manifest()
