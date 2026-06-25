import hashlib
from dataclasses import dataclass

from ncp_aai.ingestion.normalize import DocumentSegment, hash_text, normalize_text


@dataclass(frozen=True)
class Chunk:
    id: str
    source_id: str
    chunk_index: int
    text: str
    page_start: int | None
    page_end: int | None
    section: str | None
    token_count: int
    content_hash: str


def chunk_segments(
    source_id: str,
    segments: list[DocumentSegment],
    *,
    max_chars: int = 1400,
    overlap_chars: int = 180,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for segment in segments:
        text = normalize_text(segment.text)
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + max_chars)
            if end < len(text):
                split_at = text.rfind(" ", start, end)
                if split_at > start + max_chars // 2:
                    end = split_at
            chunk_text = normalize_text(text[start:end])
            if chunk_text:
                chunk_index = len(chunks)
                chunk_hash = hash_text(chunk_text)
                chunk_id = stable_chunk_id(source_id, chunk_index, chunk_hash)
                chunks.append(
                    Chunk(
                        id=chunk_id,
                        source_id=source_id,
                        chunk_index=chunk_index,
                        text=chunk_text,
                        page_start=segment.page,
                        page_end=segment.page,
                        section=segment.section,
                        token_count=len(chunk_text.split()),
                        content_hash=chunk_hash,
                    )
                )
            if end >= len(text):
                break
            start = max(end - overlap_chars, start + 1)
    return chunks


def stable_chunk_id(source_id: str, chunk_index: int, chunk_hash: str) -> str:
    raw = f"{source_id}:{chunk_index}:{chunk_hash}".encode()
    return f"chunk-{hashlib.sha256(raw).hexdigest()[:24]}"
