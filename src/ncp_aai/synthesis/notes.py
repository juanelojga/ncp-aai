import json
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select

from ncp_aai.agents.codex_provider import CodexOutputInput
from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session
from ncp_aai.models import AgentRun, Citation, Note, QuizQuestion, Topic
from ncp_aai.synthesis.citations import validate_source_chunk_ids


def ingest_codex_output(
    payload: CodexOutputInput, settings: Settings | None = None
) -> dict[str, Any]:
    settings = settings or get_settings()
    chunk_ids = [citation.source_chunk_id for citation in payload.citations]
    for quiz_item in payload.quiz_items:
        chunk_ids.extend(citation.source_chunk_id for citation in quiz_item.citations)
    validate_source_chunk_ids(chunk_ids, settings)

    topic_id = payload.topic_id or _topic_for_objective(payload.objective_id, settings)
    objective_id = payload.objective_id or _objective_for_topic(topic_id, settings)
    note_id = f"note-{uuid.uuid4().hex}"
    vault_path = write_note_file(payload, note_id, settings)
    provider = payload.provider_metadata.provider
    model = payload.provider_metadata.model

    quiz_ids: list[str] = []
    with session(settings) as db:
        db.add(
            Note(
                id=note_id,
                topic_id=topic_id,
                objective_id=objective_id,
                title=payload.title,
                body=payload.note_body,
                provider=provider,
                model=model,
                prompt_version=payload.provider_metadata.prompt_version,
                vault_path=str(vault_path),
                metadata_json=json.dumps(
                    {"gaps": payload.gaps, "provider_run_id": payload.provider_metadata.run_id}
                ),
            )
        )
        db.flush()
        for citation in payload.citations:
            db.add(
                Citation(
                    id=f"citation-{uuid.uuid4().hex}",
                    note_id=note_id,
                    source_chunk_id=citation.source_chunk_id,
                    label=citation.label,
                    quote=citation.quote,
                )
            )
        for quiz_item in payload.quiz_items:
            quiz_id = f"quiz-{uuid.uuid4().hex}"
            quiz_ids.append(quiz_id)
            db.add(
                QuizQuestion(
                    id=quiz_id,
                    topic_id=topic_id,
                    objective_id=objective_id,
                    prompt=quiz_item.prompt,
                    options_json=json.dumps(quiz_item.options),
                    correct_option=quiz_item.correct_option,
                    rationale=quiz_item.rationale,
                    difficulty=quiz_item.difficulty,
                    concept=quiz_item.concept,
                    provider=provider,
                    model=model,
                )
            )
            db.flush()
            for citation in quiz_item.citations:
                db.add(
                    Citation(
                        id=f"citation-{uuid.uuid4().hex}",
                        quiz_question_id=quiz_id,
                        source_chunk_id=citation.source_chunk_id,
                        label=citation.label,
                        quote=citation.quote,
                    )
                )
        db.add(
            AgentRun(
                id=f"run-{uuid.uuid4().hex}",
                provider=provider,
                model=model,
                prompt_version=payload.provider_metadata.prompt_version,
                input_source_ids_json=json.dumps(sorted(set(chunk_ids))),
                output_artifact_ids_json=json.dumps([note_id, *quiz_ids]),
                status="complete",
                metadata_json=json.dumps({"mode": "operator_output_ingestion"}),
            )
        )

    return {
        "note_id": note_id,
        "quiz_question_ids": quiz_ids,
        "vault_path": str(vault_path),
        "citation_count": len(payload.citations)
        + sum(len(item.citations) for item in payload.quiz_items),
    }


def write_note_file(payload: CodexOutputInput, note_id: str, settings: Settings) -> Path:
    settings.ensure_directories()
    slug = _slugify(payload.title)
    path = settings.app_vault_dir / f"{slug}-{note_id[-8:]}.md"
    frontmatter = {
        "note_id": note_id,
        "objective_id": payload.objective_id,
        "topic_id": payload.topic_id,
        "provider": payload.provider_metadata.provider,
        "model": payload.provider_metadata.model,
        "prompt_version": payload.provider_metadata.prompt_version,
    }
    content = (
        "---\n" + "\n".join(f"{key}: {value}" for key, value in frontmatter.items()) + "\n---\n\n"
    )
    path.write_text(content + payload.note_body.strip() + "\n", encoding="utf-8")
    return path


def _topic_for_objective(objective_id: str | None, settings: Settings) -> str | None:
    if objective_id is None:
        return None
    with session(settings) as db:
        return db.scalar(select(Topic.id).where(Topic.objective_id == objective_id))


def _objective_for_topic(topic_id: str | None, settings: Settings) -> str | None:
    if topic_id is None:
        return None
    with session(settings) as db:
        return db.scalar(select(Topic.objective_id).where(Topic.id == topic_id))


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "note"
