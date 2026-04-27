from typing import List

import faiss

from .embedder import Embedder
from .models import TextChunk


def retrieve(
    index: faiss.IndexFlatIP,
    embedder: Embedder,
    chunks: List[TextChunk],
    question: str,
    top_k: int,
) -> List[dict]:
    if index.ntotal == 0:
        return []

    query_vec = embedder.embed_query(question)
    faiss.normalize_L2(query_vec)

    safe_k = min(max(1, top_k), index.ntotal)
    scores, ids = index.search(query_vec, safe_k)  # type: ignore[call-arg]

    results: List[dict] = []
    for score, idx in zip(scores[0], ids[0]):
        if idx < 0 or idx >= len(chunks):
            continue
        chunk = chunks[int(idx)]
        results.append(
            {
                "chunk_id": chunk.chunk_id,
                "source": chunk.source,
                "text": chunk.text,
                "metadata": chunk.metadata,
                "score": float(score),
            }
        )
    return results
