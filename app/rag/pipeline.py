import logging
from typing import List
from urllib.parse import urlparse

from app.config import Settings

from .chunking import chunk_text
from .embedder import Embedder
from .generator import generate_grounded_answer
from .loader import load_documents
from .models import TextChunk
from .retriever import retrieve
from .vector_store import build_index, load_artifacts, save_artifacts

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def _build_context(matches: List[dict], max_chunks: int = 3) -> str:
    selected: List[str] = []
    seen = set()

    for item in matches:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        key = _normalize_text(text)
        if key in seen:
            continue
        seen.add(key)
        selected.append(text)
        if len(selected) >= max_chunks:
            break

    return "\n\n".join(selected)


def _extract_sources(matches: List[dict], max_sources: int = 5) -> List[str]:
    sources: List[str] = []
    seen = set()

    for item in matches:
        source = str(item.get("source", "")).strip()
        if not source or source in seen:
            continue
        seen.add(source)
        sources.append(source)
        if len(sources) >= max_sources:
            break

    return sources


def _extract_recommended_link(matches: List[dict]) -> str | None:
    if not matches:
        return None

    top = matches[0] or {}
    metadata = top.get("metadata") or {}

    recommended_link = str(metadata.get("recommended_link") or "").strip()
    if recommended_link:
        return recommended_link

    source_url = str(metadata.get("source_url") or "").strip()
    if source_url:
        return source_url

    source = str(top.get("source") or "").strip()
    return source or None


def _display_source_label(item: dict) -> str:
    metadata = item.get("metadata") or {}
    title = str(metadata.get("title") or "").strip()
    if title:
        return title

    source_url = str(metadata.get("source_url") or "").strip()
    recommended_link = str(metadata.get("recommended_link") or "").strip()
    fallback_source = str(item.get("source") or "").strip()

    candidate = source_url or recommended_link or fallback_source
    if not candidate:
        return ""

    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        return candidate

    path = parsed.path.strip("/")
    if not path:
        return parsed.netloc
    return path.split("/")[-1] or parsed.netloc


def _extract_display_sources(matches: List[dict], max_sources: int = 3) -> List[str]:
    labels: List[str] = []
    seen = set()

    for item in matches:
        label = _display_source_label(item)
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        labels.append(label)
        if len(labels) >= max_sources:
            break

    return labels


class RAGPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.index = None
        self.chunks: List[TextChunk] = []
        self.embedder: Embedder | None = None

    def build_from_raw(self) -> dict:
        docs = load_documents(self.settings.raw_data_dir)

        chunks: List[TextChunk] = []
        next_id = 0
        for doc in docs:
            parts = chunk_text(
                doc.text,
                chunk_size_words=self.settings.default_chunk_size_words,
                overlap_words=self.settings.default_chunk_overlap_words,
            )
            for part in parts:
                chunks.append(TextChunk(chunk_id=next_id, source=doc.source, text=part))
                next_id += 1

        if not chunks:
            raise ValueError("No chunks were generated from raw data")

        texts = [c.text for c in chunks]
        embedder, vectors = Embedder.fit(texts)
        index = build_index(vectors)

        save_artifacts(
            index=index,
            chunks=chunks,
            vectorizer=embedder.vectorizer,
            index_path=self.settings.index_path,
            chunks_path=self.settings.chunks_path,
            vectorizer_path=self.settings.vectorizer_path,
        )

        self.index = index
        self.chunks = chunks
        self.embedder = embedder

        logger.info("Built RAG index: %s chunks", len(chunks))
        return {"chunks": len(chunks), "documents": len(docs)}

    def load(self) -> None:
        index, chunks, vectorizer = load_artifacts(
            self.settings.index_path,
            self.settings.chunks_path,
            self.settings.vectorizer_path,
        )
        self.index = index
        self.chunks = chunks
        self.embedder = Embedder(vectorizer=vectorizer)

    def ensure_ready(self) -> None:
        if self.index is not None and self.embedder is not None and self.chunks:
            return

        try:
            self.load()
            logger.info("Loaded existing RAG index artifacts")
        except FileNotFoundError:
            logger.info("RAG artifacts not found; building from raw data")
            self.build_from_raw()

    def ask(self, question: str, top_k: int) -> dict:
        self.ensure_ready()
        assert self.index is not None
        assert self.embedder is not None

        matches = retrieve(
            index=self.index,
            embedder=self.embedder,
            chunks=self.chunks,
            question=question,
            top_k=max(2, top_k),
        )

        context = _build_context(matches, max_chunks=2)
        answer = generate_grounded_answer(question, context)

        cta = "If you'd like, we can start a short application flow to match you with the right mortgage path."

        if answer.count(cta) > 1:
            parts = answer.split(cta)
            answer = cta.join(parts[:2])

        return {
            "answer": answer,
            "sources": _extract_sources(matches),
            "recommended_link": _extract_recommended_link(matches),
            "display_sources": _extract_display_sources(matches, max_sources=3),
            "matches": matches,
        }
