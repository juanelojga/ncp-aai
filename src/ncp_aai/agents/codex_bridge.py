import json
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from ncp_aai.agents.codex_provider import CodexOutputInput
from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session
from ncp_aai.models import Note, Objective, SourceChunk, SourceRecord, Topic


class CodexBridgeRequest(BaseModel):
    job_id: str
    topic_id: str
    objective_id: str
    title: str
    query: str
    retrieved_chunks: list[dict[str, Any]]
    existing_notes: list[dict[str, Any]] = Field(default_factory=list)
    instructions: str


def request_dir(settings: Settings) -> Path:
    return settings.codex_output_dir / "requests"


def response_dir(settings: Settings) -> Path:
    return settings.codex_output_dir / "responses"


def schema_path(settings: Settings) -> Path:
    return settings.codex_output_dir / "codex-output.schema.json"


def ensure_bridge_directories(settings: Settings) -> None:
    settings.ensure_directories()
    request_dir(settings).mkdir(parents=True, exist_ok=True)
    response_dir(settings).mkdir(parents=True, exist_ok=True)
    schema_path(settings).write_text(
        json.dumps(CodexOutputInput.model_json_schema(), indent=2),
        encoding="utf-8",
    )


def write_codex_request(
    *,
    job_id: str,
    topic_id: str,
    query: str,
    retrieved_chunks: list[dict[str, Any]],
    settings: Settings | None = None,
) -> Path:
    settings = settings or get_settings()
    ensure_bridge_directories(settings)
    with session(settings) as db:
        topic = db.execute(
            select(Topic, Objective)
            .join(Objective, Objective.id == Topic.objective_id)
            .where(Topic.id == topic_id)
        ).first()
        if topic is None:
            msg = f"Unknown topic_id: {topic_id}"
            raise ValueError(msg)
        topic_row, objective_row = topic
        notes = db.scalars(
            select(Note).where(Note.topic_id == topic_id).order_by(desc(Note.created_at)).limit(5)
        ).all()

    request = CodexBridgeRequest(
        job_id=job_id,
        topic_id=topic_row.id,
        objective_id=topic_row.objective_id,
        title=topic_row.title,
        query=query,
        retrieved_chunks=_bridge_chunks(retrieved_chunks, settings),
        existing_notes=[
            {
                "id": note.id,
                "title": note.title,
                "body": note.body,
                "provider": note.provider,
                "created_at": note.created_at,
            }
            for note in notes
        ],
        instructions=(
            "Create a concise certification study note grounded in the provided chunks. "
            "The Markdown note_body must use these sections in this order: Practical "
            "explanation, Study guide, Key concepts, Architecture/design patterns, Examples, "
            "Tradeoffs/failure modes, Exam cues, Gaps. "
            "Return only JSON matching the supplied schema. Every note citation and quiz citation "
            "must reference a source_chunk_id from retrieved_chunks. Include provider metadata, a "
            "Markdown note_body, 2-4 quiz_items when evidence supports them, and gaps for missing "
            "or uncertain coverage. Use web search only to supplement context; source-backed "
            "claims "
            "must still cite local chunks."
        ),
    )
    path = request_dir(settings) / f"{job_id}.json"
    path.write_text(request.model_dump_json(indent=2), encoding="utf-8")
    return path


def codex_response_path(job_id: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return response_dir(settings) / f"{job_id}.json"


def load_codex_response(job_id: str, settings: Settings | None = None) -> CodexOutputInput | None:
    path = codex_response_path(job_id, settings)
    if not path.is_file():
        return None
    return CodexOutputInput.model_validate_json(path.read_text(encoding="utf-8"))


def run_codex_for_request(
    request_path: Path,
    *,
    settings: Settings | None = None,
    codex_binary: str = "codex",
) -> Path:
    settings = settings or get_settings()
    ensure_bridge_directories(settings)
    request_payload = json.loads(request_path.read_text(encoding="utf-8"))
    output_path = codex_response_path(request_payload["job_id"], settings)
    prompt = (
        "You are generating structured NCP-AAI study artifacts. "
        "Use the request JSON below and return JSON that exactly matches the output schema.\n\n"
        f"{json.dumps(request_payload, indent=2)}"
    )
    subprocess.run(
        [
            codex_binary,
            "exec",
            "--search",
            "--output-schema",
            str(schema_path(settings)),
            "-C",
            str(settings.project_root),
            "-o",
            str(output_path),
            prompt,
        ],
        check=True,
    )
    return output_path


def _bridge_chunks(chunks: list[dict[str, Any]], settings: Settings) -> list[dict[str, Any]]:
    enriched_chunks = [
        {
            "source_chunk_id": str(chunk.get("chunk_id") or chunk.get("source_chunk_id")),
            "source_id": chunk.get("source_id"),
            "source_title": chunk.get("source_title"),
            "source_path": chunk.get("source_path"),
            "source_url": chunk.get("source_url"),
            "excerpt": chunk.get("text"),
            "page_start": chunk.get("page_start"),
            "page_end": chunk.get("page_end"),
            "section": chunk.get("section"),
            "score": chunk.get("similarity", chunk.get("score")),
        }
        for chunk in chunks
    ]
    chunk_ids = [chunk["source_chunk_id"] for chunk in enriched_chunks]
    if not chunk_ids:
        return enriched_chunks

    with session(settings) as db:
        rows = db.execute(
            select(SourceChunk, SourceRecord)
            .join(SourceRecord, SourceRecord.id == SourceChunk.source_id)
            .where(SourceChunk.id.in_(chunk_ids))
        ).all()
    by_id = {source_chunk.id: (source_chunk, source_record) for source_chunk, source_record in rows}

    for enriched in enriched_chunks:
        row = by_id.get(enriched["source_chunk_id"])
        if row is None:
            continue
        source_chunk, source_record = row
        enriched.update(
            {
                "source_id": source_chunk.source_id,
                "source_title": source_record.title,
                "source_path": source_record.path,
                "source_url": source_record.url,
                "excerpt": source_chunk.text,
                "page_start": source_chunk.page_start,
                "page_end": source_chunk.page_end,
                "section": source_chunk.section,
                "chunk_metadata": json.loads(source_chunk.metadata_json),
                "source_metadata": json.loads(source_record.metadata_json),
            }
        )
    return enriched_chunks
