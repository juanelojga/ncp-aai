from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import func, select

from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session
from ncp_aai.jobs.investigation import (
    create_investigation_job,
    run_host_codex_investigation,
    run_local_investigation,
)
from ncp_aai.models import Domain, Note, Objective, QuizQuestion, Topic
from ncp_aai.objectives import import_objectives

GenerationMode = Literal["host_codex", "local_stub"]


@dataclass(frozen=True)
class DomainTopic:
    id: str
    objective_id: str
    objective_number: str
    title: str
    note_count: int
    quiz_count: int


def generate_domain_study_material(
    domain_id: str,
    *,
    mode: GenerationMode = "host_codex",
    k: int = 12,
    auto_ingest: bool = True,
    force: bool = False,
    topic_ids: list[str] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    settings.ensure_directories()
    import_objectives(settings=settings)

    topics = list_domain_topics(domain_id, topic_ids=topic_ids, settings=settings)
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for topic in topics:
        if not force and topic.note_count > 0 and topic.quiz_count > 0:
            skipped.append(_topic_summary(topic, status="skipped", reason="artifacts_exist"))
            continue

        job_id = create_investigation_job(topic_id=topic.id, query=topic.title, settings=settings)
        try:
            if mode == "local_stub":
                result = run_local_investigation(
                    topic.id,
                    query=topic.title,
                    k=k,
                    auto_ingest=auto_ingest,
                    settings=settings,
                    job_id=job_id,
                )
            else:
                result = run_host_codex_investigation(
                    topic.id,
                    query=topic.title,
                    k=k,
                    auto_ingest=auto_ingest,
                    settings=settings,
                    job_id=job_id,
                )
        except Exception as exc:  # noqa: BLE001 - batch must continue after one bad topic
            failed.append(
                _topic_summary(topic, status="failed", job_id=job_id, reason=str(exc))
            )
            continue

        created.append(
            _topic_summary(
                topic,
                status=result["status"],
                job_id=result["job_id"],
                request_path=result.get("request_path"),
                note_id=result.get("note_id"),
                quiz_question_ids=result.get("quiz_question_ids", []),
                retrieved_chunk_count=result.get("retrieved_chunk_count", 0),
            )
        )

    return {
        "domain_id": domain_id,
        "mode": mode,
        "k": k,
        "auto_ingest": auto_ingest,
        "force": force,
        "created": created,
        "skipped": skipped,
        "failed": failed,
    }


def list_domain_topics(
    domain_id: str,
    *,
    topic_ids: list[str] | None = None,
    settings: Settings | None = None,
) -> list[DomainTopic]:
    settings = settings or get_settings()
    import_objectives(settings=settings)
    requested_topic_ids = set(topic_ids or [])

    with session(settings) as db:
        domain = db.get(Domain, domain_id)
        if domain is None:
            raise ValueError(f"Unknown domain_id: {domain_id}")

        rows = db.execute(
            select(
                Topic.id,
                Topic.objective_id,
                Topic.title,
                Objective.number.label("objective_number"),
                func.count(func.distinct(Note.id)).label("note_count"),
                func.count(func.distinct(QuizQuestion.id)).label("quiz_count"),
            )
            .join(Objective, Objective.id == Topic.objective_id)
            .outerjoin(Note, Note.topic_id == Topic.id)
            .outerjoin(QuizQuestion, QuizQuestion.topic_id == Topic.id)
            .where(Objective.domain_id == domain_id)
            .group_by(Topic.id, Topic.objective_id, Topic.title, Objective.number)
        ).all()

    topics = [
        DomainTopic(
            id=row.id,
            objective_id=row.objective_id,
            objective_number=row.objective_number,
            title=row.title,
            note_count=int(row.note_count or 0),
            quiz_count=int(row.quiz_count or 0),
        )
        for row in rows
    ]
    topics.sort(key=lambda item: tuple(int(part) for part in item.objective_number.split(".")))

    if requested_topic_ids:
        known_ids = {topic.id for topic in topics}
        unknown_ids = sorted(requested_topic_ids - known_ids)
        if unknown_ids:
            raise ValueError(f"Unknown topic_id(s) for {domain_id}: {', '.join(unknown_ids)}")
        topics = [topic for topic in topics if topic.id in requested_topic_ids]

    return topics


def _topic_summary(
    topic: DomainTopic,
    *,
    status: str,
    reason: str | None = None,
    job_id: str | None = None,
    request_path: str | None = None,
    note_id: str | None = None,
    quiz_question_ids: list[str] | None = None,
    retrieved_chunk_count: int | None = None,
) -> dict[str, Any]:
    return {
        "topic_id": topic.id,
        "objective_id": topic.objective_id,
        "objective_number": topic.objective_number,
        "title": topic.title,
        "status": status,
        "reason": reason,
        "job_id": job_id,
        "request_path": request_path,
        "note_id": note_id,
        "quiz_question_ids": quiz_question_ids or [],
        "retrieved_chunk_count": retrieved_chunk_count,
    }
