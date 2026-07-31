"""CenkorMES RAG 向量搜索（ChromaDB + OpenAI 兼容 Embedding API）"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.ai.client import resolve_runtime

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "cenkormes_docs"
_BATCH_SIZE = 20
_CACHE_TTL = 300  # 5 分钟

# ── 内存缓存 ──────────────────────────────────────────────
_search_cache: dict[str, tuple[float, list[dict]]] = {}


def _cache_get(key: str) -> list[dict] | None:
    ts, val = _search_cache.get(key, (0, None))
    if time.time() - ts < _CACHE_TTL:
        return val
    _search_cache.pop(key, None)
    return None


def _cache_set(key: str, val: list[dict]) -> None:
    _search_cache[key] = (time.time(), val)


# ── Embedding 调用 ────────────────────────────────────────

def _get_embeddings(db: Session, texts: list[str], *, tenant_id: int | None = None) -> list[list[float]]:
    """通过 OpenAI 兼容 API 获取 embedding 向量。"""
    cfg = resolve_runtime(db, tenant_id=tenant_id)
    client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=cfg.timeout_seconds)
    results: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        try:
            resp = client.embeddings.create(
                model=cfg.model,
                input=batch,
            )
            for item in resp.data:
                results.append(item.embedding)
        except Exception as e:
            logger.warning("Embedding API 调用失败: %s", e[:200])
            # 返回空向量作为 fallback
            for _ in batch:
                results.append([])
    return results


# ── ChromaDB 管理 ────────────────────────────────────────

def _get_chroma_dir() -> Path:
    d = Path(settings.RAG_CHROMA_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_chroma_collection():
    """获取或创建 ChromaDB 集合（嵌入式持久化）。"""
    import chromadb

    client = chromadb.PersistentClient(path=str(_get_chroma_dir()))
    return client.get_or_create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# ── 分块 ─────────────────────────────────────────────────

@dataclass
class _DocChunk:
    source: str
    title: str
    content: str
    chunk_index: int


_TOKEN_RE = __import__("re").compile(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_./-]{2,}")


def _resolve_docs_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs"
        if candidate.is_dir() and any(candidate.glob("*.md")):
            return candidate
    return here.parents[4] / "docs"


def _split_markdown(text: str, source: str, chunk_size: int = 0, overlap: int = 0) -> list[_DocChunk]:
    """按 Markdown 标题分块，支持滑动窗口。"""
    if chunk_size <= 0:
        chunk_size = settings.RAG_CHUNK_SIZE
    if overlap <= 0:
        overlap = settings.RAG_CHUNK_OVERLAP

    lines = text.splitlines()
    chunks: list[_DocChunk] = []
    title = source
    buf: list[str] = []

    def flush():
        nonlocal buf, title
        body = "\n".join(buf).strip()
        if len(body) < 40:
            buf = []
            return
        # 如果 body 超过 chunk_size，进一步按段落切分
        if len(body) <= chunk_size:
            chunks.append(_DocChunk(source=source, title=title, content=body[:3000], chunk_index=len(chunks)))
        else:
            # 滑动窗口切分
            start = 0
            sub_idx = 0
            while start < len(body):
                end = min(start + chunk_size, len(body))
                chunk_text = body[start:end]
                if start > 0:
                    # 添加 overlap 上下文
                    overlap_start = max(0, start - overlap)
                    chunk_text = body[overlap_start:end]
                chunks.append(_DocChunk(source=source, title=title, content=chunk_text[:3000], chunk_index=len(chunks)))
                start += chunk_size - overlap
                sub_idx += 1
                if sub_idx > 50:  # 安全限制
                    break
        buf = []

    for line in lines:
        if line.startswith("#"):
            flush()
            title = line.lstrip("#").strip() or source
            buf = [line]
        else:
            buf.append(line)
    flush()
    if not chunks and text.strip():
        body = text.strip()[:3000]
        chunks.append(_DocChunk(source=source, title=source, content=body, chunk_index=0))
    return chunks


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text)}


# ── 索引构建 ─────────────────────────────────────────────

def build_vector_index(db: Session, *, force: bool = False, tenant_id: int | None = None) -> int:
    """构建向量索引：读取 docs/*.md -> 分块 -> embedding -> 存入 ChromaDB。"""
    docs_dir = _resolve_docs_dir()
    if not docs_dir.is_dir():
        logger.warning("文档目录不存在: %s", docs_dir)
        return 0

    all_chunks: list[_DocChunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        all_chunks.extend(_split_markdown(text, path.name))

    if not all_chunks:
        return 0

    # 获取已有文档签名，判断是否需要重建
    collection = _get_chroma_collection()
    existing_ids = set()
    try:
        existing = collection.get(include=[])
        existing_ids = set(existing["ids"])
    except Exception:
        pass

    # 计算每个 chunk 的唯一 ID
    chunk_entries: list[tuple[str, _DocChunk]] = []
    for ch in all_chunks:
        content_hash = hashlib.md5(ch.content.encode()).hexdigest()[:12]
        chunk_id = f"{ch.source}::{ch.chunk_index}::{content_hash}"
        chunk_entries.append((chunk_id, ch))

    # 过滤已存在的 chunk（增量更新）
    if not force:
        chunk_entries = [(cid, ch) for cid, ch in chunk_entries if cid not in existing_ids]

    if not chunk_entries:
        logger.info("向量索引已是最新，共 %d chunks", len(existing_ids))
        return len(existing_ids)

    # 批量 embedding
    texts = [ch.content for _, ch in chunk_entries]
    embeddings = _get_embeddings(db, texts, tenant_id=tenant_id)

    # 过滤掉 embedding 失败的（空向量）
    valid_entries = [(cid, ch, emb) for (cid, ch), emb in zip(chunk_entries, embeddings) if emb]

    if not valid_entries:
        logger.warning("所有 embedding 调用失败，索引未更新")
        return len(existing_ids)

    # 存入 ChromaDB
    ids = [cid for cid, _, _ in valid_entries]
    documents = [ch.content for _, ch, _ in valid_entries]
    metadatas = [
        {"source": ch.source, "title": ch.title, "chunk_index": ch.chunk_index}
        for _, ch, _ in valid_entries
    ]
    embed_vectors = [emb for _, _, emb in valid_entries]

    # 分批 upsert（ChromaDB 单次限制）
    upsert_batch = 100
    for i in range(0, len(ids), upsert_batch):
        batch_ids = ids[i : i + upsert_batch]
        batch_docs = documents[i : i + upsert_batch]
        batch_meta = metadatas[i : i + upsert_batch]
        batch_emb = embed_vectors[i : i + upsert_batch]
        try:
            collection.upsert(
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_meta,
                embeddings=batch_emb,
            )
        except Exception as e:
            logger.error("ChromaDB upsert 失败: %s", e[:200])

    total = len(existing_ids) + len(valid_entries)
    logger.info("向量索引构建完成: 新增 %d chunks，总计 %d", len(valid_entries), total)
    return total


# ── 语义搜索 ─────────────────────────────────────────────

def semantic_search(
    db: Session,
    query: str,
    *,
    top_k: int = 5,
    tenant_id: int | None = None,
) -> list[dict]:
    """向量语义搜索。"""
    cache_key = f"rag:v:{query[:100]}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        collection = _get_chroma_collection()
        count = collection.count()
        if count == 0:
            return []
    except Exception as e:
        logger.warning("ChromaDB 不可用: %s", e[:200])
        return []

    # 查询 embedding
    embeddings = _get_embeddings(db, [query], tenant_id=tenant_id)
    if not embeddings or not embeddings[0]:
        return []

    query_embedding = embeddings[0]

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.warning("ChromaDB 查询失败: %s", e[:200])
        return []

    items = []
    if results and results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            dist = results["distances"][0][i] if results["distances"] else 1.0
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            doc = results["documents"][0][i] if results["documents"] else ""
            # cosine distance -> similarity score (0~1)
            similarity = max(0.0, 1.0 - dist)
            items.append(
                {
                    "source": meta.get("source", ""),
                    "title": meta.get("title", ""),
                    "snippet": doc[:480],
                    "score": round(similarity, 4),
                    "chunk_index": meta.get("chunk_index", 0),
                }
            )

    _cache_set(cache_key, items)
    return items


def hybrid_search(
    db: Session,
    query: str,
    *,
    top_k: int = 5,
    tenant_id: int | None = None,
    keyword_weight: float | None = None,
) -> list[dict]:
    """混合搜索：向量 + 关键词加权融合。"""
    from app.services.ai.rag_help import search_docs as keyword_search

    if keyword_weight is None:
        keyword_weight = 1.0 - settings.RAG_HYBRID_WEIGHT

    vector_results = semantic_search(db, query, top_k=top_k * 2, tenant_id=tenant_id)
    keyword_results = keyword_search(query, top_k=top_k * 2)

    # 归一化分数到 0~1
    v_max = max((r["score"] for r in vector_results), default=1.0) or 1.0
    k_max = max((r["score"] for r in keyword_results), default=1.0) or 1.0

    scored: dict[str, dict] = {}
    for r in vector_results:
        key = f"{r['source']}::{r.get('chunk_index', 0)}"
        scored[key] = {**r, "_vscore": r["score"] / v_max, "_kscore": 0.0}

    for r in keyword_results:
        key = f"{r['source']}::0"
        if key in scored:
            scored[key]["_kscore"] = r["score"] / k_max
        else:
            scored[key] = {**r, "_vscore": 0.0, "_kscore": r["score"] / k_max}

    # 加权融合
    vw = settings.RAG_HYBRID_WEIGHT
    for item in scored.values():
        item["score"] = round(item["_vscore"] * vw + item["_kscore"] * keyword_weight, 4)

    merged = sorted(scored.values(), key=lambda x: x["score"], reverse=True)
    result = []
    seen_sources = set()
    for item in merged:
        src = item.get("source", "")
        if src not in seen_sources or len(result) < top_k:
            result.append({k: v for k, v in item.items() if not k.startswith("_")})
            seen_sources.add(src)
        if len(result) >= top_k:
            break

    return result
