from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    text: str
    char_start: int
    char_end: int


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[TextChunk]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    safe_overlap = max(0, min(overlap, max(chunk_size - 1, 0)))
    step = max(1, chunk_size - safe_overlap)
    chunks: list[TextChunk] = []
    cursor = 0
    chunk_index = 0

    while cursor < len(cleaned):
        end = min(len(cleaned), cursor + chunk_size)
        piece = cleaned[cursor:end].strip()
        if piece:
            chunks.append(
                TextChunk(
                    chunk_index=chunk_index,
                    text=piece,
                    char_start=cursor,
                    char_end=end,
                )
            )
            chunk_index += 1
        if end >= len(cleaned):
            break
        cursor += step

    return chunks
