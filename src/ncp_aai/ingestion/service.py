import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session
from ncp_aai.ingestion.chunking import chunk_segments
from ncp_aai.ingestion.normalize import DocumentSegment, hash_bytes, hash_text, segment_text
from ncp_aai.ingestion.readers import SUPPORTED_EXTENSIONS, read_document
from ncp_aai.models import SourceChunk, SourceRecord, Topic, TopicSource, VectorEntry
from ncp_aai.rag.store import RagStore


def resolve_inbox_path(relative_path: str, settings: Settings) -> Path:
    candidate = (settings.app_inbox_dir / relative_path).resolve()
    inbox_root = settings.app_inbox_dir.resolve()
    if inbox_root not in candidate.parents and candidate != inbox_root:
        msg = "Source path must be inside the configured inbox directory"
        raise ValueError(msg)
    if not candidate.exists():
        msg = f"Inbox source does not exist: {relative_path}"
        raise FileNotFoundError(msg)
    return candidate


def ingest_inbox_file(
    relative_path: str,
    *,
    source_type: str = "local_file",
    objective_ids: list[str] | None = None,
    topic_ids: list[str] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    return ingest_local_file(
        resolve_inbox_path(relative_path, settings),
        source_type=source_type,
        objective_ids=objective_ids,
        topic_ids=topic_ids,
        settings=settings,
    )


def ingest_local_file(
    path: Path,
    *,
    source_type: str = "local_file",
    objective_ids: list[str] | None = None,
    topic_ids: list[str] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        msg = f"Unsupported source extension: {path.suffix}"
        raise ValueError(msg)

    file_bytes = path.read_bytes()
    content_hash = hash_bytes(file_bytes)
    source_id = f"source-{content_hash[:24]}"
    segments = read_document(path)
    normalized_text = segment_text(segments)
    title = path.stem.replace("-", " ").replace("_", " ").strip() or path.name
    topic_ids = _resolve_topic_ids(objective_ids or [], topic_ids or [], settings)

    with session(settings) as db:
        existing = db.scalar(
            select(SourceRecord.id).where(SourceRecord.content_hash == content_hash)
        )
        if existing:
            source_id = existing
            for topic_id in topic_ids:
                db.execute(
                    sqlite_insert(TopicSource)
                    .values(topic_id=topic_id, source_id=source_id)
                    .on_conflict_do_nothing()
                )
            chunk_count = db.scalar(
                select(func.count())
                .select_from(SourceChunk)
                .where(SourceChunk.source_id == source_id)
            )
            vector_count = db.scalar(
                select(func.count())
                .select_from(VectorEntry)
                .join(SourceChunk, SourceChunk.id == VectorEntry.source_chunk_id)
                .where(SourceChunk.source_id == source_id)
            )
            return {
                "source_id": source_id,
                "chunk_count": chunk_count or 0,
                "vector_count": vector_count or 0,
                "deduplicated": True,
            }

        db.add(
            SourceRecord(
                id=source_id,
                source_type=source_type,
                title=title,
                path=str(path),
                content_type=path.suffix.lower().lstrip(".") or "text",
                content_hash=content_hash,
                metadata_json=json.dumps({"normalized_characters": len(normalized_text)}),
            )
        )
        db.flush()
        chunks = chunk_segments(source_id, segments)
        for chunk in chunks:
            db.add(
                SourceChunk(
                    id=chunk.id,
                    source_id=chunk.source_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    section=chunk.section,
                    token_count=chunk.token_count,
                    content_hash=chunk.content_hash,
                    metadata_json=json.dumps({}),
                )
            )
        db.flush()
        for topic_id in topic_ids:
            db.execute(
                sqlite_insert(TopicSource)
                .values(topic_id=topic_id, source_id=source_id)
                .on_conflict_do_nothing()
            )

    vector_count = RagStore(settings).index_chunks(
        [
            {
                "id": chunk.id,
                "text": chunk.text,
                "metadata": {
                    "source_id": source_id,
                    "page_start": chunk.page_start,
                    "section": chunk.section,
                },
            }
            for chunk in chunks
        ]
    )
    return {
        "source_id": source_id,
        "chunk_count": len(chunks),
        "vector_count": vector_count,
        "deduplicated": False,
    }


def ingest_text_source(
    *,
    title: str,
    text: str,
    source_type: str,
    content_type: str = "text",
    url: str | None = None,
    path: str | None = None,
    topic_ids: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    segments = [DocumentSegment(text=text, section=title)]
    normalized_text = segment_text(segments)
    content_hash = hash_text(normalized_text)
    source_id = f"source-{content_hash[:24]}"
    topic_ids = _resolve_topic_ids([], topic_ids or [], settings)
    metadata_payload = {
        "normalized_characters": len(normalized_text),
        **(metadata or {}),
    }

    with session(settings) as db:
        existing = db.scalar(
            select(SourceRecord.id).where(SourceRecord.content_hash == content_hash)
        )
        if existing:
            source_id = existing
            for topic_id in topic_ids:
                db.execute(
                    sqlite_insert(TopicSource)
                    .values(topic_id=topic_id, source_id=source_id)
                    .on_conflict_do_nothing()
                )
            chunk_count = db.scalar(
                select(func.count())
                .select_from(SourceChunk)
                .where(SourceChunk.source_id == source_id)
            )
            vector_count = db.scalar(
                select(func.count())
                .select_from(VectorEntry)
                .join(SourceChunk, SourceChunk.id == VectorEntry.source_chunk_id)
                .where(SourceChunk.source_id == source_id)
            )
            return {
                "source_id": source_id,
                "chunk_count": chunk_count or 0,
                "vector_count": vector_count or 0,
                "deduplicated": True,
            }

        db.add(
            SourceRecord(
                id=source_id,
                source_type=source_type,
                title=title,
                path=path,
                url=url,
                content_type=content_type,
                content_hash=content_hash,
                metadata_json=json.dumps(metadata_payload),
            )
        )
        db.flush()
        chunks = chunk_segments(source_id, segments)
        for chunk in chunks:
            db.add(
                SourceChunk(
                    id=chunk.id,
                    source_id=chunk.source_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    section=chunk.section,
                    token_count=chunk.token_count,
                    content_hash=chunk.content_hash,
                    metadata_json=json.dumps({}),
                )
            )
        db.flush()
        for topic_id in topic_ids:
            db.execute(
                sqlite_insert(TopicSource)
                .values(topic_id=topic_id, source_id=source_id)
                .on_conflict_do_nothing()
            )

    vector_count = RagStore(settings).index_chunks(
        [
            {
                "id": chunk.id,
                "text": chunk.text,
                "metadata": {
                    "source_id": source_id,
                    "page_start": chunk.page_start,
                    "section": chunk.section,
                },
            }
            for chunk in chunks
        ]
    )
    return {
        "source_id": source_id,
        "chunk_count": len(chunks),
        "vector_count": vector_count,
        "deduplicated": False,
    }


def _resolve_topic_ids(
    objective_ids: list[str], topic_ids: list[str], settings: Settings
) -> list[str]:
    resolved = set(topic_ids)
    if not objective_ids:
        return sorted(resolved)
    with session(settings) as db:
        for objective_id in objective_ids:
            topic_id = db.scalar(select(Topic.id).where(Topic.objective_id == objective_id))
            if topic_id:
                resolved.add(topic_id)
    return sorted(resolved)
