"""Async knowledge store backed by ChromaDB (OpenCLAW 0.7).

All Chroma I/O runs in :func:`asyncio.to_thread` so callers can use async APIs.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings, Space

from core.org_tree import OrgTree


def _encode_tags(tags: list[str]) -> str:
    return "|".join(sorted({t.strip() for t in tags if t.strip()}))


def _decode_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [x for x in str(raw).split("|") if x]


def _flatten_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Chroma metadata values must be scalar; JSON-encode the rest."""
    out: dict[str, str | int | float | bool] = {}
    for k, v in metadata.items():
        if k in ("tags", "org_path"):
            continue
        if isinstance(v, (str, int, float, bool)):
            out[str(k)] = v
        else:
            out[str(k)] = json.dumps(v, ensure_ascii=False)
    return out


def _tags_intersect(stored: list[str], required: list[str]) -> bool:
    """If ``required`` is empty, do not filter by tags."""
    if not required:
        return True
    return bool(set(stored) & set(required))


def _tags_visible_for_org_path(tags: list[str], org_path: str) -> bool:
    """Simple rule: a tag matches if it appears in the path or equals a segment."""
    if not org_path:
        return True
    parts = [p for p in org_path.strip("/").split("/") if p]
    for t in tags:
        if t in org_path:
            return True
        if t in parts:
            return True
    return False


class DeterministicHashEmbeddingFunction(EmbeddingFunction[Documents]):
    """Fixed-size deterministic vectors (no network). Replace with a real model in production."""

    def __init__(self, dimensions: int = 64) -> None:
        self._dims = dimensions

    def __call__(self, input: Documents) -> Embeddings:
        import hashlib

        out: list[np.ndarray] = []
        for text in input:
            h = hashlib.sha256(text.encode("utf-8")).digest()
            vec: list[float] = []
            for i in range(self._dims):
                b0 = h[i % len(h)]
                b1 = h[(i * 3 + 1) % len(h)]
                vec.append((b0 + b1) / 510.0 - 1.0)
            out.append(np.array(vec, dtype=np.float32))
        return out

    @staticmethod
    def name() -> str:
        return "zhiweitong_deterministic_hash"

    def default_space(self) -> Space:
        return "cosine"

    def supported_spaces(self) -> list[Space]:
        return ["cosine", "l2", "ip"]

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> EmbeddingFunction[Documents]:
        dim = int(config.get("dimensions", 64))
        return DeterministicHashEmbeddingFunction(dimensions=dim)

    def get_config(self) -> dict[str, Any]:
        return {"dimensions": self._dims}


class KnowledgeStore:
    """Vector knowledge base with tag + org_path filtering.

    Defaults to :class:`DeterministicHashEmbeddingFunction` so tests and CI do not
    download ONNX models; pass ``embedding_function=`` with a Chroma-compatible
    model (e.g. OpenAI / HuggingFace) in production.
    """

    DEFAULT_COLLECTION = "zhiweitong_knowledge"

    def __init__(
        self,
        *,
        persist_directory: str | Path | None = None,
        collection_name: str = DEFAULT_COLLECTION,
        org_tree: OrgTree | None = None,
        embedding_function: Any | None = None,
    ) -> None:
        import chromadb

        self._org_tree = org_tree
        ef = embedding_function or DeterministicHashEmbeddingFunction()
        if persist_directory is not None:
            p = Path(persist_directory)
            p.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(p))
        else:
            self._client = chromadb.Client()
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "智维通默认知识库"},
            embedding_function=ef,
        )

    def _validate_reader_org_path(self, org_path: str | None) -> None:
        if self._org_tree is None:
            return
        if org_path is None:
            raise ValueError("org_path is required when org_tree is configured")
        self._org_tree.get_meta(org_path)

    def _validate_writer_org_path(self, org_path: str | None) -> None:
        if self._org_tree is None or org_path is None:
            return
        self._org_tree.get_meta(org_path)

    async def store(
        self,
        tags: list[str],
        content: str,
        metadata: dict[str, Any],
        *,
        org_path: str | None = None,
    ) -> str:
        """Embed ``content``, store with ``tags`` and flattened ``metadata``; returns ``doc_id``."""
        self._validate_writer_org_path(org_path)

        doc_id = str(uuid.uuid4())
        meta: dict[str, str | int | float | bool] = dict(_flatten_metadata(metadata))
        meta["tags"] = _encode_tags(tags)
        if org_path is not None:
            meta["org_path"] = org_path

        def _add() -> None:
            self._collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[meta],
            )

        await asyncio.to_thread(_add)
        return doc_id

    async def retrieve(
        self,
        tags: list[str],
        query: str,
        top_k: int = 5,
        *,
        org_path: str | None = None,
        oversample: int = 8,
    ) -> list[dict[str, Any]]:
        """Semantic search, then filter by tag intersection and org_path/tag matching."""
        self._validate_reader_org_path(org_path)

        def _count() -> int:
            return int(self._collection.count())

        n_docs = await asyncio.to_thread(_count)
        if n_docs == 0 or top_k <= 0:
            return []

        n_fetch = min(max(top_k * oversample, top_k), n_docs)

        def _query() -> dict[str, Any]:
            return self._collection.query(
                query_texts=[query],
                n_results=n_fetch,
                include=["documents", "metadatas", "distances"],
            )

        raw = await asyncio.to_thread(_query)
        ids_list = raw["ids"][0]
        docs_list = raw["documents"][0]
        metas_list = raw["metadatas"][0]
        dists = raw.get("distances")
        dist_list = dists[0] if dists else [0.0] * len(ids_list)

        out: list[dict[str, Any]] = []
        for i, doc_id in enumerate(ids_list):
            meta_row = dict(metas_list[i]) if metas_list[i] else {}
            stored_tags = _decode_tags(str(meta_row.get("tags", "")))
            if not _tags_intersect(stored_tags, tags):
                continue
            doc_org = meta_row.get("org_path")
            if (
                org_path is not None
                and isinstance(doc_org, str)
                and doc_org
                and not (org_path.startswith(doc_org) or doc_org.startswith(org_path))
            ):
                continue
            user_meta = {
                k: v
                for k, v in meta_row.items()
                if k not in ("tags", "org_path")
            }
            out.append(
                {
                    "doc_id": doc_id,
                    "content": docs_list[i],
                    "metadata": user_meta,
                    "tags": stored_tags,
                    "distance": float(dist_list[i]) if dist_list[i] is not None else 0.0,
                },
            )
            if len(out) >= top_k:
                break
        return out

    async def update(
        self,
        doc_id: str,
        *,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        org_path: str | None = None,
    ) -> None:
        """Update one document; unspecified fields are kept."""
        self._validate_writer_org_path(org_path)

        def _get() -> dict[str, Any]:
            return self._collection.get(ids=[doc_id], include=["documents", "metadatas"])

        got = await asyncio.to_thread(_get)
        if not got["ids"]:
            raise KeyError(f"unknown doc_id: {doc_id!r}")

        cur_doc = got["documents"][0]
        cur_meta = dict(got["metadatas"][0] or {})

        new_doc = cur_doc if content is None else content
        new_meta = dict(cur_meta)
        if tags is not None:
            new_meta["tags"] = _encode_tags(tags)
        if org_path is not None:
            new_meta["org_path"] = org_path
        if metadata:
            for k, v in _flatten_metadata(metadata).items():
                new_meta[k] = v

        def _upd() -> None:
            self._collection.update(
                ids=[doc_id],
                documents=[new_doc],
                metadatas=[new_meta],
            )

        await asyncio.to_thread(_upd)

    async def delete(self, doc_id: str) -> None:
        """Delete by id; raises ``KeyError`` if missing."""
        def _get() -> dict[str, Any]:
            return self._collection.get(ids=[doc_id])

        got = await asyncio.to_thread(_get)
        if not got["ids"]:
            raise KeyError(f"unknown doc_id: {doc_id!r}")

        await asyncio.to_thread(partial(self._collection.delete, ids=[doc_id]))

    async def aclose(self) -> None:
        """Reserved for future resource cleanup; Chroma clients need no explicit close."""
        return
