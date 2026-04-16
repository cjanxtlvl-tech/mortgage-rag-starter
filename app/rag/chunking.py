from typing import List


def chunk_text(text: str, chunk_size_words: int, overlap_words: int) -> List[str]:
    words = text.split()
    if not words:
        return []

    step = max(1, chunk_size_words - overlap_words)
    chunks: List[str] = []

    for start in range(0, len(words), step):
        end = start + chunk_size_words
        piece = " ".join(words[start:end]).strip()
        if piece:
            chunks.append(piece)
        if end >= len(words):
            break

    return chunks
