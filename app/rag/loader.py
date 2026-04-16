import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .models import RawDocument


TEXT_KEYS = ("text", "content", "body", "answer", "description")
TITLE_KEYS = ("title", "topic", "question", "name")


def _compose_text(item: Dict[str, Any]) -> str:
    title_parts = [str(item[k]).strip() for k in TITLE_KEYS if k in item and str(item[k]).strip()]
    text_parts = [str(item[k]).strip() for k in TEXT_KEYS if k in item and str(item[k]).strip()]
    merged = "\n".join([p for p in title_parts + text_parts if p])
    return merged.strip()


def _items_from_payload(payload: Any) -> Iterable[str]:
    if isinstance(payload, str):
        val = payload.strip()
        if val:
            yield val
        return

    if isinstance(payload, dict):
        text = _compose_text(payload)
        if text:
            yield text
        for value in payload.values():
            if isinstance(value, (list, tuple)):
                for nested in value:
                    if isinstance(nested, dict):
                        nested_text = _compose_text(nested)
                        if nested_text:
                            yield nested_text
                    elif isinstance(nested, str) and nested.strip():
                        yield nested.strip()
        return

    if isinstance(payload, list):
        for item in payload:
            yield from _items_from_payload(item)


def load_documents(raw_dir: Path) -> List[RawDocument]:
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw data directory not found: {raw_dir}")

    documents: List[RawDocument] = []
    for path in sorted(raw_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        for text in _items_from_payload(payload):
            if text:
                documents.append(RawDocument(source=path.name, text=text))

    if not documents:
        raise ValueError(f"No text content found in JSON files under: {raw_dir}")

    return documents
