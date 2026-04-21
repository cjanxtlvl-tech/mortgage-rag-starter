"""Structured logging for RAG request/response cycle."""

import json
import logging
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)


def log_ask_request(
    request_id: str,
    question: str,
    response_type: str,
    answer: str,
    suggested_next_action: str | None = None,
    retrieval_info: dict[str, Any] | None = None,
) -> None:
    """
    Log a structured request with full retrieval details for debugging/analytics.
    
    This captures detailed information that is NOT returned to the public API response,
    including similarity scores, all chunks, and internal details.
    
    Args:
        request_id: Unique request identifier for correlation
        question: User's original question
        response_type: Route type (rag_response, start_application, etc.)
        answer: Generated or routing answer
        suggested_next_action: Optional routing action
        retrieval_info: Detailed retrieval info including chunks with scores
    """
    log_data = {
        "request_id": request_id,
        "timestamp": datetime.utcnow().isoformat(),
        "question": question,
        "response_type": response_type,
        "answer": answer,
        "suggested_next_action": suggested_next_action,
    }

    if retrieval_info:
        chunks = retrieval_info.get("chunks")
        if chunks is None:
            chunks = retrieval_info.get("matches", [])
        if chunks is None:
            chunks = []

        log_data["retrieval"] = {
            "model_used": retrieval_info.get("model_used"),
            "top_k_requested": retrieval_info.get("top_k_requested"),
            "matches_returned": retrieval_info.get("matches_returned", len(chunks)),
            "chunks_retrieved": len(chunks),
            "sources_returned": retrieval_info.get("sources_returned", []),
            "sources_filtered": retrieval_info.get("sources_filtered", []),
            "chunks": chunks,
        }

    logger.info("RAG_REQUEST: %s", json.dumps(log_data, indent=2))


def log_retrieval_debug(
    request_id: str,
    question: str,
    matches: list[dict[str, Any]],
    top_k_requested: int,
) -> dict[str, Any]:
    """
    Extract and structure detailed retrieval information for logging.
    
    Args:
        request_id: Request correlation ID
        question: Original user question
        matches: Retrieved chunks with similarity scores
        top_k_requested: Number of chunks requested
        
    Returns:
        dict: Structured retrieval info including chunks with scores
    """
    chunks_detail = []
    for i, match in enumerate(matches):
        chunk_info = {
            "rank": i + 1,
            "source": match.get("source", "unknown"),
            "chunk_id": match.get("chunk_id"),
            "score": match.get("score", 0),
            "preview": match.get("text", "")[:200],  # First 200 chars
        }
        chunks_detail.append(chunk_info)

    return {
        "request_id": request_id,
        "question": question,
        "top_k_requested": top_k_requested,
        "matches_returned": len(matches),
        "chunks": chunks_detail,
    }


def log_non_rag_route(
    request_id: str,
    question: str,
    route_type: str,
    reason: str = "",
) -> None:
    """
    Log non-RAG routing decisions (e.g., start_application, clarify_goal).
    
    Args:
        request_id: Request correlation ID
        question: Original user question
        route_type: Routing decision (start_application, etc.)
        reason: Optional explanation for the routing decision
    """
    logger.info(
        "RAG_NON_RAG_ROUTE",
        extra={
            "request_id": request_id,
            "question": question,
            "route_type": route_type,
            "reason": reason,
        },
    )
