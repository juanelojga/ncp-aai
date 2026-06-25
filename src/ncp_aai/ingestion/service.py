import json
from pathlib import Path
from typing import Any

from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session
from ncp_aai.ingestion.chunking import chunk_segments
from ncp_aai.ingestion.normalize import hash_bytes, segment_text
from ncp_aai.ingestion.readers import SUPPORTED_EXTENSIONS, read_document
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

    with session(settings) as conn:
        existing = conn.execute(
            "SELECT id FROM source_records WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        if existing:
            source_id = existing["id"]
            for topic_id in topic_ids:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO topic_sources (topic_id, source_id)
                    VALUES (?, ?)
                    """,
                    (topic_id, source_id),
                )
            chunk_count = conn.execute(
                "SELECT COUNT(*) AS count FROM source_chunks WHERE source_id = ?", (source_id,)
            ).fetchone()["count"]
            vector_count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM vector_entries ve
                JOIN source_chunks sc ON sc.id = ve.source_chunk_id
                WHERE sc.source_id = ?
                """,
                (source_id,),
            ).fetchone()["count"]
            return {
                "source_id": source_id,
                "chunk_count": chunk_count,
                "vector_count": vector_count,
                "deduplicated": True,
            }

        conn.execute(
            """
            INSERT INTO source_records
                (id, source_type, title, path, content_type, content_hash, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                source_type,
                title,
                str(path),
                path.suffix.lower().lstrip(".") or "text",
                content_hash,
                json.dumps({"normalized_characters": len(normalized_text)}),
            ),
        )
        chunks = chunk_segments(source_id, segments)
        for chunk in chunks:
            conn.execute(
                """
                INSERT INTO source_chunks
                    (id, source_id, chunk_index, text, page_start, page_end, section,
                     token_count, content_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.id,
                    chunk.source_id,
                    chunk.chunk_index,
                    chunk.text,
                    chunk.page_start,
                    chunk.page_end,
                    chunk.section,
                    chunk.token_count,
                    chunk.content_hash,
                    json.dumps({}),
                ),
            )
        for topic_id in topic_ids:
            conn.execute(
                "INSERT OR IGNORE INTO topic_sources (topic_id, source_id) VALUES (?, ?)",
                (topic_id, source_id),
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
    with session(settings) as conn:
        for objective_id in objective_ids:
            row = conn.execute(
                "SELECT id FROM topics WHERE objective_id = ?", (objective_id,)
            ).fetchone()
            if row:
                resolved.add(row["id"])
    return sorted(resolved)
