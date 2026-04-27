import json
import pickle
from pathlib import Path
from typing import List

import faiss
import numpy as np

from .models import TextChunk


def build_index(vectors: np.ndarray) -> faiss.IndexFlatIP:
    if vectors.ndim != 2 or vectors.shape[0] == 0:
        raise ValueError("Vectors must be a 2D matrix with at least one row")

    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    faiss.normalize_L2(vectors)
    index.add(vectors)
    return index


def save_artifacts(
    index: faiss.IndexFlatIP,
    chunks: List[TextChunk],
    vectorizer,
    index_path: Path,
    chunks_path: Path,
    vectorizer_path: Path,
) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_path))

    payload = [
        {
            "chunk_id": c.chunk_id,
            "source": c.source,
            "text": c.text,
            "metadata": c.metadata,
        }
        for c in chunks
    ]
    chunks_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with vectorizer_path.open("wb") as handle:
        pickle.dump(vectorizer, handle)


def load_artifacts(index_path: Path, chunks_path: Path, vectorizer_path: Path):
    if not (index_path.exists() and chunks_path.exists() and vectorizer_path.exists()):
        raise FileNotFoundError("Index artifacts are missing. Run scripts/process_data.py first.")

    index = faiss.read_index(str(index_path))

    raw_chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    chunks = [
        TextChunk(
            chunk_id=int(item["chunk_id"]),
            source=item["source"],
            text=item["text"],
            metadata=item.get("metadata", {}) or {},
        )
        for item in raw_chunks
    ]

    with vectorizer_path.open("rb") as handle:
        vectorizer = pickle.load(handle)

    return index, chunks, vectorizer
