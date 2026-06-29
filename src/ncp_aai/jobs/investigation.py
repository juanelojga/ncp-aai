import difflib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, text, update

from ncp_aai.agents.codex_bridge import load_codex_response, write_codex_request
from ncp_aai.agents.codex_provider import CodexOutputInput
from ncp_aai.agents.local_stub import build_stub_codex_output
from ncp_aai.config import Settings, get_settings
from ncp_aai.db import model_to_dict, session
from ncp_aai.ingestion.service import ingest_local_file
from ncp_aai.models import InvestigationJob, Objective, SourceChunk, Topic, TopicSource
from ncp_aai.objectives import import_objectives
from ncp_aai.rag.store import RagStore
from ncp_aai.synthesis.notes import ingest_codex_output

TERMINAL_STATUSES = {"complete", "failed", "needs_review"}


class InvestigationError(ValueError):
    pass


class AmbiguousTopicError(InvestigationError):
    def __init__(self, topic_ref: str, candidates: list[dict[str, str]]) -> None:
        self.topic_ref = topic_ref
        self.candidates = candidates
        labels = ", ".join(f"{item['id']} ({item['title']})" for item in candidates)
        super().__init__(f"Ambiguous topic reference '{topic_ref}'. Candidates: {labels}")


class TopicNotFoundError(InvestigationError):
    pass


class SourceUnavailableError(InvestigationError):
    pass


@dataclass(frozen=True)
class ResolvedTopic:
    id: str
    objective_id: str
    objective_number: str
    title: str


def run_local_investigation(
    topic_ref: str,
    *,
    query: str | None = None,
    k: int = 5,
    auto_ingest: bool = True,
    settings: Settings | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    settings.ensure_directories()
    import_objectives(settings=settings)

    topic = resolve_topic(topic_ref, settings)
    investigation_query = query or topic.title
    job_id = job_id or create_investigation_job(
        topic_id=topic.id,
        query=investigation_query,
        settings=settings,
    )

    try:
        _update_job(
            job_id,
            settings,
            status="collecting_sources",
            log="Checking local sources for resolved topic.",
        )
        ingest_result = None
        if _linked_chunk_count(topic.id, settings) == 0:
            if not auto_ingest:
                raise SourceUnavailableError(
                    f"No indexed source chunks found for {topic.id}; ingest sources first "
                    "or rerun with auto-ingest."
                )
            ingest_result = ingest_local_file(
                settings.bundled_study_guide_path,
                source_type="study_guide_pdf",
                objective_ids=[topic.objective_id],
                topic_ids=[topic.id],
                settings=settings,
            )
            _update_job(
                job_id,
                settings,
                status="collecting_sources",
                log=(
                    "Auto-ingested bundled study guide "
                    f"({ingest_result['chunk_count']} chunks, "
                    f"deduplicated={ingest_result['deduplicated']})."
                ),
            )

        results = RagStore(settings).query(investigation_query, k=k, topic_id=topic.id)
        if not results:
            raise SourceUnavailableError(f"No retrievable chunks found for {topic.id}.")

        _update_job(
            job_id,
            settings,
            status="extracting",
            log=f"Retrieved {len(results)} local chunks.",
        )
        _update_job(
            job_id,
            settings,
            status="synthesizing",
            log="Generating local grounded study artifacts.",
        )

        stub_payload = build_stub_codex_output(
            objective_id=topic.objective_id,
            topic_id=topic.id,
            title=f"Study Investigation: {topic.title}",
            retrieved_chunks=results,
        )
        result = ingest_codex_output(stub_payload, settings)
        artifacts = [result["note_id"], *result["quiz_question_ids"]]
        _update_job(
            job_id,
            settings,
            status="complete",
            log="Generated and persisted local grounded study artifacts.",
            gaps=stub_payload.gaps,
            artifacts=artifacts,
            complete=True,
        )
        job = get_investigation_job(job_id, settings)
        return {
            "job_id": job_id,
            "status": job["status"],
            "topic_id": topic.id,
            "objective_id": topic.objective_id,
            "query": investigation_query,
            "note_id": result["note_id"],
            "quiz_question_ids": result["quiz_question_ids"],
            "vault_path": result["vault_path"],
            "citation_count": result["citation_count"],
            "retrieved_chunk_count": len(results),
            "ingest": ingest_result,
            "logs": job["logs"],
            "gaps": job["gaps"],
            "artifact_ids": job["artifact_ids"],
        }
    except Exception as exc:
        _update_job(
            job_id,
            settings,
            status="failed",
            error=str(exc),
            log=f"Job failed: {exc}",
            complete=True,
        )
        raise


def run_host_codex_investigation(
    topic_ref: str,
    *,
    query: str | None = None,
    k: int = 12,
    auto_ingest: bool = True,
    settings: Settings | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    settings.ensure_directories()
    import_objectives(settings=settings)

    topic = resolve_topic(topic_ref, settings)
    investigation_query = query or topic.title
    job_id = job_id or create_investigation_job(
        topic_id=topic.id,
        query=investigation_query,
        settings=settings,
    )

    try:
        _update_job(
            job_id,
            settings,
            status="collecting_sources",
            log="Checking local sources for host Codex synthesis.",
        )
        ingest_result = None
        if _linked_chunk_count(topic.id, settings) == 0:
            if not auto_ingest:
                raise SourceUnavailableError(
                    f"No indexed source chunks found for {topic.id}; ingest sources first "
                    "or rerun with auto-ingest."
                )
            ingest_result = ingest_local_file(
                settings.bundled_study_guide_path,
                source_type="study_guide_pdf",
                objective_ids=[topic.objective_id],
                topic_ids=[topic.id],
                settings=settings,
            )
            _update_job(
                job_id,
                settings,
                status="collecting_sources",
                log=(
                    "Auto-ingested bundled study guide "
                    f"({ingest_result['chunk_count']} chunks, "
                    f"deduplicated={ingest_result['deduplicated']})."
                ),
            )

        results = RagStore(settings).query(investigation_query, k=k, topic_id=topic.id)
        if not results:
            raise SourceUnavailableError(f"No retrievable chunks found for {topic.id}.")

        _update_job(
            job_id,
            settings,
            status="extracting",
            log=f"Retrieved {len(results)} local chunks for host Codex request.",
        )
        request_path = write_codex_request(
            job_id=job_id,
            topic_id=topic.id,
            query=investigation_query,
            retrieved_chunks=results,
            settings=settings,
        )
        _update_job(
            job_id,
            settings,
            status="synthesizing",
            log=f"Wrote host Codex request: {request_path}",
        )

        def _host_result(job: dict[str, Any], **extra: Any) -> dict[str, Any]:
            return {
                "job_id": job_id,
                "status": job["status"],
                "topic_id": topic.id,
                "objective_id": topic.objective_id,
                "query": investigation_query,
                "request_path": str(request_path),
                "retrieved_chunk_count": len(results),
                "ingest": ingest_result,
                "logs": job["logs"],
                "gaps": job["gaps"],
                "artifact_ids": job["artifact_ids"],
                **extra,
            }

        response = load_codex_response(job_id, settings)
        if response is None:
            _update_job(
                job_id,
                settings,
                status="needs_review",
                log=(
                    "Waiting for host Codex bridge. Start `uv run ncp-aai codex-worker` "
                    f"and retry after {job_id}.json appears in the responses directory."
                ),
                gaps=["Host Codex bridge response is required to finish synthesis."],
                complete=True,
            )
            return _host_result(get_investigation_job(job_id, settings))

        result = ingest_codex_payload_for_job(job_id, response, settings)
        return _host_result(
            get_investigation_job(job_id, settings),
            note_id=result["note_id"],
            quiz_question_ids=result["quiz_question_ids"],
            vault_path=result["vault_path"],
            citation_count=result["citation_count"],
        )
    except Exception as exc:
        _update_job(
            job_id,
            settings,
            status="failed",
            error=str(exc),
            log=f"Job failed: {exc}",
            complete=True,
        )
        raise


def ingest_operator_output_for_job(
    job_id: str,
    codex_output: dict[str, Any],
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    _update_job(job_id, settings, status="synthesizing", log="Validating operator output.")
    codex_payload = CodexOutputInput.model_validate(codex_output)
    return ingest_codex_payload_for_job(job_id, codex_payload, settings)


def ingest_codex_payload_for_job(
    job_id: str,
    codex_payload: CodexOutputInput,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    result = ingest_codex_output(codex_payload, settings)
    artifacts = [result["note_id"], *result["quiz_question_ids"]]
    _update_job(
        job_id,
        settings,
        status="complete",
        log="Validated and persisted Codex output.",
        gaps=codex_payload.gaps,
        artifacts=artifacts,
        complete=True,
    )
    return result


def create_investigation_job(
    *,
    topic_id: str | None,
    query: str,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    job_id = f"job-{uuid.uuid4().hex}"
    with session(settings) as db:
        db.add(
            InvestigationJob(
                id=job_id,
                topic_id=topic_id,
                status="queued",
                query=query,
                logs_json=json.dumps(["Queued investigation job."]),
            )
        )
    return job_id


def resolve_topic(topic_ref: str, settings: Settings | None = None) -> ResolvedTopic:
    settings = settings or get_settings()
    normalized_ref = _normalize(topic_ref)
    with session(settings) as db:
        direct = db.execute(
            select(Topic.id, Topic.objective_id, Objective.number, Topic.title)
            .join(Objective, Objective.id == Topic.objective_id)
            .where(Topic.id == topic_ref)
        ).first()
        if direct:
            return _resolved_from_row(direct)

        rows = db.execute(
            select(Topic.id, Topic.objective_id, Objective.number, Topic.title).join(
                Objective, Objective.id == Topic.objective_id
            )
        ).all()

    candidates = [
        {
            "id": row.id,
            "objective_id": row.objective_id,
            "objective_number": row.number,
            "title": row.title,
            "normalized_title": _normalize(row.title),
        }
        for row in rows
    ]
    exact = [item for item in candidates if item["normalized_title"] == normalized_ref]
    if len(exact) == 1:
        return _resolved_from_candidate(exact[0])
    if len(exact) > 1:
        raise AmbiguousTopicError(topic_ref, _public_candidates(exact))

    contains = [
        item
        for item in candidates
        if normalized_ref in item["normalized_title"] or item["normalized_title"] in normalized_ref
    ]
    if len(contains) == 1:
        return _resolved_from_candidate(contains[0])
    if len(contains) > 1:
        raise AmbiguousTopicError(topic_ref, _public_candidates(contains[:5]))

    scored = sorted(
        (
            (difflib.SequenceMatcher(None, normalized_ref, item["normalized_title"]).ratio(), item)
            for item in candidates
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    if scored and scored[0][0] >= 0.72:
        if len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.08:
            return _resolved_from_candidate(scored[0][1])
        raise AmbiguousTopicError(topic_ref, _public_candidates([item for _, item in scored[:5]]))

    raise TopicNotFoundError(f"Unknown topic reference: {topic_ref}")


def get_investigation_job(job_id: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    with session(settings) as db:
        row = db.get(InvestigationJob, job_id)
    if row is None:
        raise TopicNotFoundError(f"Unknown job_id: {job_id}")
    job = model_to_dict(row)
    job["logs"] = json.loads(job.pop("logs_json"))
    job["gaps"] = json.loads(job.pop("gaps_json"))
    job["artifact_ids"] = json.loads(job.pop("artifact_ids_json"))
    return job


def mark_job_needs_review(
    job_id: str,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    _update_job(
        job_id,
        settings,
        status="needs_review",
        log="Local retrieval complete; submit Codex output to finish synthesis.",
        gaps=["Operator Codex output is required for synthesized notes/quizzes."],
        complete=True,
    )


def _linked_chunk_count(topic_id: str, settings: Settings) -> int:
    with session(settings) as db:
        return (
            db.scalar(
                select(func.count())
                .select_from(SourceChunk)
                .join(TopicSource, TopicSource.source_id == SourceChunk.source_id)
                .where(TopicSource.topic_id == topic_id)
            )
            or 0
        )


def _update_job(
    job_id: str,
    settings: Settings,
    *,
    status: str,
    log: str | None = None,
    gaps: list[str] | None = None,
    artifacts: list[str] | None = None,
    error: str | None = None,
    complete: bool = False,
) -> None:
    with session(settings) as db:
        job = db.get(InvestigationJob, job_id)
        if job is None:
            return
        logs = json.loads(job.logs_json)
        if log:
            logs.append(log)
        current_gaps = json.loads(job.gaps_json)
        if gaps:
            current_gaps.extend(gaps)
        current_artifacts = json.loads(job.artifact_ids_json)
        if artifacts:
            current_artifacts.extend(artifacts)

        values = {
            "status": status,
            "logs_json": json.dumps(logs),
            "gaps_json": json.dumps(current_gaps),
            "artifact_ids_json": json.dumps(current_artifacts),
            "error": error,
            "updated_at": text("CURRENT_TIMESTAMP"),
        }
        if complete:
            values["completed_at"] = text("CURRENT_TIMESTAMP")
        else:
            values["started_at"] = text("COALESCE(started_at, CURRENT_TIMESTAMP)")
        db.execute(update(InvestigationJob).where(InvestigationJob.id == job_id).values(**values))


def _resolved_from_row(row: Any) -> ResolvedTopic:
    return ResolvedTopic(
        id=row.id,
        objective_id=row.objective_id,
        objective_number=row.number,
        title=row.title,
    )


def _resolved_from_candidate(candidate: dict[str, str]) -> ResolvedTopic:
    return ResolvedTopic(
        id=candidate["id"],
        objective_id=candidate["objective_id"],
        objective_number=candidate["objective_number"],
        title=candidate["title"],
    )


def _public_candidates(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "id": item["id"],
            "objective_id": item["objective_id"],
            "title": item["title"],
        }
        for item in candidates
    ]


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())
