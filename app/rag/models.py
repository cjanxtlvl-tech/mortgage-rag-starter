from dataclasses import dataclass


@dataclass
class RawDocument:
    source: str
    text: str


@dataclass
class TextChunk:
    chunk_id: int
    source: str
    text: str
