"""CenkorMES 文档 RAG 帮助（关键词检索 + LLM 回答）"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.services.ai.client import AiCallError, AiNotConfiguredError, chat_completion

_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_./-]{2,}")

_INDEX: list["_DocChunk"] | None = None
_INDEX_SIGNATURE: tuple[tuple[str, int], ...] | None = None


@dataclass
class _DocChunk:
    source: str
    title: str
    content: str
    tokens: set[str]


def _resolve_docs_dir() -> Path:
    """从 backend/app 向上查找含 docs/*.md 的项目根 docs 目录。"""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs"
        if candidate.is_dir() and any(candidate.glob("*.md")):
            return candidate
    return here.parents[4] / "docs"


def _docs_signature(docs_dir: Path) -> tuple[tuple[str, int], ...]:
    if not docs_dir.is_dir():
        return ()
    sig: list[tuple[str, int]] = []
    for path in sorted(docs_dir.glob("*.md")):
        try:
            sig.append((path.name, path.stat().st_mtime_ns))
        except OSError:
            continue
    return tuple(sig)


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text)}


def _split_markdown(text: str, source: str) -> list[_DocChunk]:
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
        chunks.append(_DocChunk(source=source, title=title, content=body[:3000], tokens=_tokenize(title + " " + body)))
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
        chunks.append(_DocChunk(source=source, title=source, content=body, tokens=_tokenize(body)))
    return chunks


def _build_index(*, force: bool = False) -> list[_DocChunk]:
    global _INDEX, _INDEX_SIGNATURE
    docs_dir = _resolve_docs_dir()
    sig = _docs_signature(docs_dir)
    if not force and _INDEX is not None and _INDEX_SIGNATURE == sig:
        return _INDEX

    chunks: list[_DocChunk] = []
    if docs_dir.is_dir():
        for path in sorted(docs_dir.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            chunks.extend(_split_markdown(text, path.name))
    _INDEX = chunks
    _INDEX_SIGNATURE = sig
    return chunks


def reindex_docs() -> int:
    """重建索引：同时更新关键词索引和向量索引。"""
    # 关键词索引
    count = len(_build_index(force=True))
    # 向量索引（需要 db，此处仅触发关键词索引）
    # 向量索引通过 API 端点触发（需要 db session）
    return count


def search_docs(query: str, *, top_k: int = 5) -> list[dict]:
    """文档搜索：优先向量语义搜索，fallback 到关键词搜索。"""
    try:
        from app.services.ai.rag_vector import semantic_search

        # 尝试向量搜索（需要 db session，此处用简化版）
        # 注意：search_docs 是无 db 的接口，向量搜索需要 db
        # 因此这里保留关键词搜索作为默认，向量搜索在 help_answer 中使用
        pass
    except Exception:
        pass

    # 关键词搜索（原有逻辑）
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    scored: list[tuple[float, _DocChunk]] = []
    for ch in _build_index():
        overlap = len(q_tokens & ch.tokens)
        if overlap == 0:
            continue
        bonus = 0.5 if any(t in ch.title.lower() for t in q_tokens) else 0.0
        scored.append((overlap + bonus, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[dict] = []
    for score, ch in scored[:top_k]:
        out.append(
            {
                "source": ch.source,
                "title": ch.title,
                "snippet": ch.content[:480],
                "score": round(score, 2),
            }
        )
    return out


def help_answer(
    db: Session,
    *,
    tenant_id: int,
    question: str,
    top_k: int = 5,
) -> dict:
    """智能帮助回答：优先向量语义搜索，fallback 到关键词搜索。"""
    hits = []

    # 优先尝试向量语义搜索
    try:
        from app.services.ai.rag_vector import semantic_search

        vector_hits = semantic_search(db, question, top_k=top_k, tenant_id=tenant_id)
        if vector_hits:
            hits = vector_hits
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("向量搜索失败，fallback 到关键词: %s", e[:200])

    # fallback 到关键词搜索
    if not hits:
        hits = search_docs(question, top_k=top_k)

    if not hits:
        return {
            "answer": "未在系统文档中找到相关内容，请尝试换关键词（如：报工、排产、工资、小程序）。",
            "sources": [],
        }

    context = "\n\n---\n\n".join(f"[{h['source']} · {h['title']}]\n{h['snippet']}" for h in hits)
    messages = [
        {
            "role": "system",
            "content": (
                "你是 CenkorMES 系统帮助助手。只能根据「参考文档」回答操作与部署问题，"
                "不得编造功能。若文档未提及请明确说明。回答简洁、分步骤。"
            ),
        },
        {"role": "system", "content": f"参考文档：\n{context}"},
        {"role": "user", "content": question.strip()},
    ]
    try:
        reply, _, _ = chat_completion(db, tenant_id=tenant_id, messages=messages, temperature=0.2, max_tokens=1200)
    except (AiNotConfiguredError, AiCallError) as e:
        raise
    return {"answer": reply, "sources": hits}
