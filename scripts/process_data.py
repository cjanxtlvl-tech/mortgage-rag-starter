from pathlib import Path
import json
import pickle
import sys
from typing import Any

import faiss

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.rag.embedder import Embedder
from app.rag.vector_store import build_index


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    cleaned = " ".join(str(value).split()).strip()
    return cleaned.encode("utf-8", "ignore").decode("utf-8")


def _clean_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for item in value:
        cleaned = _clean_text(item)
        if cleaned:
            tags.append(cleaned)
    return tags


def _normalize_for_dedupe(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def _load_payload(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("data", "records", "entries", "items"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]

    raise ValueError(f"Unsupported JSON format in {path}. Expected a list of objects.")


def _build_chunk(entry: dict[str, Any], fallback_id: str) -> dict[str, Any] | None:
    question = _clean_text(entry.get("question"))
    answer = _clean_text(entry.get("answer"))
    source_url = _clean_text(entry.get("source_url"))
    recommended_link = _clean_text(entry.get("recommended_link"))
    title = _clean_text(entry.get("title"))
    category = _clean_text(entry.get("category"))
    location = _clean_text(entry.get("location"))

    if not question or not answer:
        return None

    parts = [f"Q: {question}", f"A: {answer}"]
    if category:
        parts.append(f"Category: {category}")
    if location:
        parts.append(f"Location: {location}")
    combined = " ".join(parts).strip()

    source = source_url or recommended_link or title
    if not source:
        return None

    normalized_entry = {
        key: _clean_text(value) if isinstance(value, (str, int, float, bool)) or value is None else value
        for key, value in entry.items()
    }

    metadata = {
        "id": _clean_text(entry.get("id")) or fallback_id,
        "source_id": _clean_text(entry.get("source_id")),
        "question": question,
        "answer": answer,
        "source_url": source_url,
        "recommended_link": recommended_link,
        "category": category,
        "intent": _clean_text(entry.get("intent")),
        "location": location,
        "tags": _clean_tags(entry.get("tags")),
        "title": title,
    }

    for key, value in normalized_entry.items():
        if key not in metadata:
            metadata[key] = value

    return {"source": source, "text": combined, "metadata": metadata}


def _validate_chunks_payload(chunks: list[dict[str, Any]]) -> str:
    serialized = json.dumps(chunks, ensure_ascii=False, indent=2)
    loaded_back = json.loads(serialized)

    if not isinstance(loaded_back, list):
        raise ValueError("Invalid chunks payload: expected a list.")

    for idx, item in enumerate(loaded_back):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid chunk at index {idx}: expected object.")
        if not isinstance(item.get("chunk_id"), int):
            raise ValueError(f"Invalid chunk at index {idx}: missing/invalid chunk_id.")
        if not _clean_text(item.get("source")):
            raise ValueError(f"Invalid chunk at index {idx}: missing source.")
        if not _clean_text(item.get("text")):
            raise ValueError(f"Invalid chunk at index {idx}: missing text.")
        if not isinstance(item.get("metadata"), dict):
            raise ValueError(f"Invalid chunk at index {idx}: missing metadata.")

    return serialized


def main() -> None:
    settings = get_settings()
    json_files = sorted(settings.raw_data_dir.glob("*.json"))
    output_index_path = PROJECT_ROOT / "data" / "mortgage.index.faiss"
    output_chunks_path = PROJECT_ROOT / "data" / "mortgage_chunks.json"

    if not json_files:
        raise FileNotFoundError(f"No JSON files found in: {settings.raw_data_dir}")

    all_entries: list[dict[str, Any]] = []
    loaded_file_count = 0
    failed_file_count = 0

    for file_path in json_files:
        print(f"Loading file: {file_path}")
        try:
            entries = _load_payload(file_path)
        except Exception as exc:  # continue processing other files on failure
            failed_file_count += 1
            print(f"WARNING: Failed to load {file_path}: {exc}")
            continue

        loaded_file_count += 1
        all_entries.extend(entries)
        print(f"  -> records loaded: {len(entries)}")

    print(f"Total files discovered: {len(json_files)}")
    print(f"Total files loaded: {loaded_file_count}")
    print(f"Total files failed: {failed_file_count}")
    print(f"Total records loaded: {len(all_entries)}")

    chunks: list[dict[str, Any]] = []
    seen_records: set[tuple[str, str, str, str, str]] = set()
    skipped = 0
    total_processed = 0

    for i, entry in enumerate(all_entries, start=1):
        total_processed += 1
        chunk = _build_chunk(entry, fallback_id=f"qa-{i}")

        if chunk is None:
            skipped += 1
            continue

        metadata = chunk["metadata"]
        dedupe_key = (
            _normalize_for_dedupe(str(metadata.get("question", ""))),
            _normalize_for_dedupe(str(metadata.get("answer", ""))),
            _normalize_for_dedupe(str(metadata.get("category", ""))),
            _normalize_for_dedupe(str(metadata.get("location", ""))),
            _normalize_for_dedupe(str(chunk.get("source", ""))),
        )

        if dedupe_key in seen_records:
            skipped += 1
            continue

        seen_records.add(dedupe_key)
        chunks.append(chunk)

    chunks = [
        {
            "chunk_id": idx,
            "source": chunk["source"],
            "text": chunk["text"],
            "metadata": chunk["metadata"],
        }
        for idx, chunk in enumerate(chunks)
    ]

    print(f"Total chunks created: {len(chunks)}")
    print(f"Skipped records: {skipped}")
    print(f"Total records processed: {total_processed}")

    for i, sample in enumerate(chunks[:3], start=1):
        print(f"Sample embedding {i}: {sample['text']}")

    if not chunks:
        raise ValueError("No valid chunks were produced from loaded JSON files.")

    texts = [chunk["text"] for chunk in chunks]
    embedder, vectors = Embedder.fit(texts)
    index = build_index(vectors)

    if index.ntotal != len(chunks):
        raise ValueError(
            f"Alignment check failed: index vectors={index.ntotal}, chunks={len(chunks)}"
        )

    serialized_chunks = _validate_chunks_payload(chunks)

    output_index_path.parent.mkdir(parents=True, exist_ok=True)
    output_chunks_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(output_index_path))
    output_chunks_path.write_text(serialized_chunks, encoding="utf-8")

    settings.index_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(settings.index_path))
    settings.chunks_path.write_text(serialized_chunks, encoding="utf-8")

    with settings.vectorizer_path.open("wb") as handle:
        pickle.dump(embedder.vectorizer, handle)

    print(f"FAISS index saved: {output_index_path}")
    print(f"Chunks JSON saved: {output_chunks_path}")
    print(f"App index mirror: {settings.index_path}")
    print(f"App chunks mirror: {settings.chunks_path}")
    print(f"Vectorizer file: {settings.vectorizer_path}")
    print(f"Final summary -> files loaded: {loaded_file_count}, records processed: {total_processed}, chunks created: {len(chunks)}")


if __name__ == "__main__":
    main()
