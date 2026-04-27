from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawDocument:
    source: str
    text: str


@dataclass
class TextChunk:
    chunk_id: int
    source: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
