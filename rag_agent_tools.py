from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from agents import function_tool
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
RAG_TOOLS_ROOT = PROJECT_ROOT / "rag_tools"
RAG_LIB_PATH = RAG_TOOLS_ROOT / "lib"
RAG_INDEX_BASE = RAG_TOOLS_ROOT / "output" / "composite_v2_index"

load_dotenv(PROJECT_ROOT / ".env")

if str(RAG_LIB_PATH) not in sys.path:
    sys.path.append(str(RAG_LIB_PATH))

from rag_system import RAGSystem  # noqa: E402


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value is not None and value.strip():
            return value
    return None


def _resolve_provider() -> str:
    return _first_non_empty(
        os.getenv("RAG_LLM_PROVIDER"),
        os.getenv("LLM_PROVIDER"),
        "openai",
    ) or "openai"


def _normalize_top_k(top_k: int) -> int:
    return max(1, min(int(top_k), 20))


@lru_cache(maxsize=1)
def _get_rag_system() -> RAGSystem:
    provider = _resolve_provider()
    return RAGSystem(
        model_path="",
        embedding_dimension=None,
        llm_provider=provider,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=_first_non_empty(
            os.getenv("RAG_OPENAI_MODEL"),
            os.getenv("OPENAI_MODEL"),
            "gpt-5.4-mini",
        ),
        ollama_url=_first_non_empty(
            os.getenv("OLLAMA_URL"),
            os.getenv("OLLAMA_BASE_URL"),
        ),
        ollama_model=os.getenv("OLLAMA_MODEL"),
        index_file_path=str(RAG_INDEX_BASE),
    )


def _format_sources(retrieved: list[dict[str, Any]], max_chars: int = 700) -> str:
    lines: list[str] = []
    for idx, ref in enumerate(retrieved, start=1):
        text = str(ref.get("text", "")).replace("\n", " ").strip()
        if len(text) > max_chars:
            text = f"{text[:max_chars]}..."
        lines.append(
            f"{idx}. source={ref.get('source', '')}, "
            f"distance={float(ref.get('distance', 0.0)):.4f}\n{text}"
        )
    return "\n\n".join(lines)


def rag_index_status_impl() -> dict[str, Any]:
    index_path = RAG_INDEX_BASE.with_suffix(".index")
    pickle_path = RAG_INDEX_BASE.with_suffix(".pickle")
    status: dict[str, Any] = {
        "index_base": str(RAG_INDEX_BASE),
        "index_exists": index_path.exists(),
        "pickle_exists": pickle_path.exists(),
        "provider": _resolve_provider(),
        "embedding_model": None,
        "embedding_dimension": None,
        "vectors": 0,
        "texts": 0,
        "ready": False,
    }

    if not status["index_exists"] or not status["pickle_exists"]:
        return status

    try:
        rag = _get_rag_system()
        status.update(
            {
                "embedding_model": rag.embedding_model,
                "embedding_dimension": rag.embedding_dimension,
                "vectors": int(getattr(rag.index, "ntotal", 0)),
                "texts": len(rag.id_to_text),
                "ready": bool(getattr(rag.index, "ntotal", 0)),
            }
        )
    except Exception as exc:
        status["error"] = str(exc)

    return status


def rag_retrieve_impl(query: str, top_k: int = 5) -> dict[str, Any]:
    rag = _get_rag_system()
    top_k = _normalize_top_k(top_k)
    q_emb = rag.get_embedding(query)
    if not q_emb.any():
        return {
            "query": query,
            "answer": "無法為查詢生成 embedding，請確認 embedding service / model 可用。",
            "retrieved": [],
            "error": rag.last_embedding_error,
        }

    distances, indices = rag.index.search(np.array([q_emb], dtype=np.float32), top_k)
    node_ids = list(rag.id_to_text.keys())
    retrieved: list[dict[str, Any]] = []
    for idx, distance in zip(indices[0].tolist(), distances[0].tolist()):
        if idx < 0 or idx >= len(node_ids):
            continue
        node_id = node_ids[idx]
        retrieved.append(
            {
                "text": rag.id_to_text[node_id],
                "source": rag.id_to_source[node_id],
                "distance": float(distance),
                "image_count": len(rag.id_to_images.get(node_id, [])),
            }
        )

    return {
        "query": query,
        "top_k": top_k,
        "retrieved": retrieved,
    }


def rag_search_impl(query: str, top_k: int = 5) -> str:
    rag = _get_rag_system()
    results = rag.query(query, _normalize_top_k(top_k))
    answer = results.get("answer", "")
    retrieved = results.get("retrieved", [])
    sources = _format_sources(retrieved)
    if not sources:
        return str(answer)
    return f"Answer:\n{answer}\n\nSources:\n{sources}"


@function_tool(defer_loading=True)
def rag_search(query: str, top_k: int = 5) -> str:
    """Use the local RAG index to answer a question and include source excerpts."""
    return rag_search_impl(query, top_k)


@function_tool(defer_loading=True)
def rag_retrieve(query: str, top_k: int = 5) -> dict[str, Any]:
    """Retrieve source chunks from the local RAG index without generating a final answer."""
    return rag_retrieve_impl(query, top_k)


@function_tool(defer_loading=True)
def rag_index_status() -> dict[str, Any]:
    """Check whether the local RAG index is available and loaded."""
    return rag_index_status_impl()
