import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi import Path as ApiPath
from pydantic import BaseModel, Field

from ncp_aai import __version__
from ncp_aai.agents.codex_provider import CodexOperatorProvider, CodexOutputInput
from ncp_aai.agents.local_stub import build_stub_codex_output
from ncp_aai.config import Settings, get_settings
from ncp_aai.db import init_db, session
from ncp_aai.ingestion.service import ingest_inbox_file, ingest_local_file
from ncp_aai.jobs.queue import InvestigationWorker
from ncp_aai.objectives import import_objectives
from ncp_aai.rag.store import RagStore
from ncp_aai.synthesis.citations import CitationValidationError
from ncp_aai.synthesis.notes import ingest_codex_output
from ncp_aai.synthesis.quizzes import grade_quiz_attempt

worker: InvestigationWorker | None = None


def settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_dep)]


@asynccontextmanager
async def lifespan(_: FastAPI):
    global worker
    settings = get_settings()
    init_db(settings)
    worker = InvestigationWorker(settings)
    worker.start()
    try:
        yield
    finally:
        worker.stop()


app = FastAPI(title="NCP-AAI Study Backend", version=__version__, lifespan=lifespan)


class HealthResponse(BaseModel):
    status: str
    version: str
    database: dict[str, Any]
    vector_store: dict[str, Any]
    paths: dict[str, str]


class SourceIngestRequest(BaseModel):
    path: str
    source_type: str = "local_file"
    objective_ids: list[str] = Field(default_factory=list)
    topic_ids: list[str] = Field(default_factory=list)


class RagQueryRequest(BaseModel):
    query: str
    k: int = Field(default=5, ge=1, le=25)
    objective_id: str | None = None
    topic_id: str | None = None


class InvestigationRequest(BaseModel):
    query: str | None = None
    codex_output: dict[str, Any] | None = None


class QuizAttemptRequest(BaseModel):
    quiz_question_id: str
    selected_option: int = Field(ge=0, le=3)


class FeedbackRequest(BaseModel):
    body: str
    create_followup_job: bool = False


class SliceRunRequest(BaseModel):
    source_path: str | None = None
    source_in_inbox: bool = False
    objective_id: str = "objective-1.1"
    topic_id: str | None = "topic-1.1"
    query: str = "agent architecture and human agent interaction"


@app.get("/health")
def health(settings: SettingsDep) -> HealthResponse:
    try:
        with session(settings) as conn:
            conn.execute("SELECT 1").fetchone()
        database_status = "ok"
    except Exception as exc:
        database_status = f"error: {exc}"

    store = RagStore(settings)
    return HealthResponse(
        status="ok" if database_status == "ok" else "degraded",
        version=__version__,
        database={"status": database_status, "path": str(settings.sqlite_path)},
        vector_store={
            "status": "ok",
            "backend": store.backend_name,
            "path": str(settings.chroma_dir),
        },
        paths={
            "data": str(settings.app_data_dir),
            "vault": str(settings.app_vault_dir),
            "inbox": str(settings.app_inbox_dir),
            "artifacts": str(settings.app_artifact_dir),
        },
    )


@app.post("/admin/import-objectives")
def import_objectives_endpoint(settings: SettingsDep) -> dict[str, Any]:
    init_db(settings)
    return import_objectives(settings=settings)


@app.get("/api/objectives")
def list_objectives(settings: SettingsDep) -> dict[str, Any]:
    with session(settings) as conn:
        domain_rows = conn.execute("SELECT * FROM domains ORDER BY number").fetchall()
        objective_rows = conn.execute(
            """
            SELECT
                o.*,
                t.id AS topic_id,
                COUNT(DISTINCT ts.source_id) AS source_count,
                COUNT(DISTINCT n.id) AS note_count,
                COUNT(DISTINCT qq.id) AS quiz_count,
                (
                    SELECT qa.score
                    FROM quiz_attempts qa
                    WHERE qa.objective_id = o.id
                    ORDER BY qa.created_at DESC
                    LIMIT 1
                ) AS latest_quiz_score
            FROM objectives o
            LEFT JOIN topics t ON t.objective_id = o.id
            LEFT JOIN topic_sources ts ON ts.topic_id = t.id
            LEFT JOIN notes n ON n.objective_id = o.id
            LEFT JOIN quiz_questions qq ON qq.objective_id = o.id
            GROUP BY o.id, t.id
            ORDER BY CAST(substr(o.number, 1, instr(o.number, '.') - 1) AS INTEGER),
                     CAST(substr(o.number, instr(o.number, '.') + 1) AS INTEGER)
            """
        ).fetchall()
        settings_rows = conn.execute("SELECT key, value FROM app_settings").fetchall()

    objectives_by_domain: dict[str, list[dict[str, Any]]] = {}
    for row in objective_rows:
        objective = dict(row)
        objective["source_count"] = int(objective["source_count"] or 0)
        objective["note_count"] = int(objective["note_count"] or 0)
        objective["quiz_count"] = int(objective["quiz_count"] or 0)
        objectives_by_domain.setdefault(objective["domain_id"], []).append(objective)

    domains = []
    for row in domain_rows:
        domain = dict(row)
        domain["objectives"] = objectives_by_domain.get(domain["id"], [])
        domains.append(domain)

    return {
        "domains": domains,
        "metadata": {row["key"]: json.loads(row["value"]) for row in settings_rows},
    }


@app.post("/api/sources/ingest")
def ingest_source(request: SourceIngestRequest, settings: SettingsDep) -> dict[str, Any]:
    try:
        return ingest_inbox_file(
            request.path,
            source_type=request.source_type,
            objective_ids=request.objective_ids,
            topic_ids=request.topic_ids,
            settings=settings,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rag/query")
def query_rag(request: RagQueryRequest, settings: SettingsDep) -> dict[str, Any]:
    results = RagStore(settings).query(
        request.query,
        k=request.k,
        objective_id=request.objective_id,
        topic_id=request.topic_id,
    )
    return {"query": request.query, "results": results}


@app.post("/api/agent-outputs/codex")
def ingest_codex_output_endpoint(
    payload: CodexOutputInput,
    settings: SettingsDep,
) -> dict[str, Any]:
    try:
        return ingest_codex_output(payload, settings)
    except CitationValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/topics/{topic_id}/investigations")
def start_investigation(
    topic_id: Annotated[str, ApiPath()],
    request: InvestigationRequest,
    settings: SettingsDep,
) -> dict[str, str]:
    with session(settings) as conn:
        topic = conn.execute("SELECT title FROM topics WHERE id = ?", (topic_id,)).fetchone()
    if topic is None:
        raise HTTPException(status_code=404, detail=f"Unknown topic_id: {topic_id}")
    query = request.query or topic["title"]
    if worker is None:
        raise HTTPException(status_code=503, detail="Investigation worker is not running")
    job_id = worker.enqueue(topic_id=topic_id, query=query, codex_output=request.codex_output)
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/investigations/{job_id}")
def get_investigation(job_id: Annotated[str, ApiPath()], settings: SettingsDep) -> dict[str, Any]:
    with session(settings) as conn:
        row = conn.execute("SELECT * FROM investigation_jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    job = dict(row)
    job["logs"] = json.loads(job.pop("logs_json"))
    job["gaps"] = json.loads(job.pop("gaps_json"))
    job["artifact_ids"] = json.loads(job.pop("artifact_ids_json"))
    return job


@app.get("/api/topics/{topic_id}")
def get_topic(topic_id: Annotated[str, ApiPath()], settings: SettingsDep) -> dict[str, Any]:
    with session(settings) as conn:
        topic = conn.execute(
            """
            SELECT
                t.*,
                o.number AS objective_number,
                o.title AS objective_title,
                d.name AS domain_name
            FROM topics t
            JOIN objectives o ON o.id = t.objective_id
            JOIN domains d ON d.id = o.domain_id
            WHERE t.id = ?
            """,
            (topic_id,),
        ).fetchone()
        if topic is None:
            raise HTTPException(status_code=404, detail=f"Unknown topic_id: {topic_id}")
        notes = conn.execute(
            "SELECT * FROM notes WHERE topic_id = ? ORDER BY created_at DESC",
            (topic_id,),
        ).fetchall()
        sources = conn.execute(
            """
            SELECT sr.*
            FROM source_records sr
            JOIN topic_sources ts ON ts.source_id = sr.id
            WHERE ts.topic_id = ?
            ORDER BY sr.created_at DESC
            """,
            (topic_id,),
        ).fetchall()
        quizzes = conn.execute(
            "SELECT * FROM quiz_questions WHERE topic_id = ? ORDER BY created_at DESC",
            (topic_id,),
        ).fetchall()
        exercises = conn.execute(
            "SELECT * FROM exercise_recommendations WHERE topic_id = ? ORDER BY created_at DESC",
            (topic_id,),
        ).fetchall()
        feedback = conn.execute(
            "SELECT * FROM feedback_items WHERE topic_id = ? ORDER BY created_at DESC", (topic_id,)
        ).fetchall()
        jobs = conn.execute(
            "SELECT * FROM investigation_jobs WHERE topic_id = ? ORDER BY created_at DESC",
            (topic_id,),
        ).fetchall()
    return {
        "topic": dict(topic),
        "notes": [dict(row) for row in notes],
        "sources": [dict(row) for row in sources],
        "quiz_questions": [_decode_quiz(row) for row in quizzes],
        "exercises": [dict(row) for row in exercises],
        "feedback": [dict(row) for row in feedback],
        "jobs": [_decode_job(row) for row in jobs],
    }


@app.post("/api/quiz-attempts")
def create_quiz_attempt(request: QuizAttemptRequest, settings: SettingsDep) -> dict[str, Any]:
    try:
        return grade_quiz_attempt(
            quiz_question_id=request.quiz_question_id,
            selected_option=request.selected_option,
            settings=settings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/topics/{topic_id}/feedback")
def create_feedback(
    topic_id: Annotated[str, ApiPath()],
    request: FeedbackRequest,
    settings: SettingsDep,
) -> dict[str, Any]:
    followup_job_id = None
    if request.create_followup_job:
        if worker is None:
            raise HTTPException(status_code=503, detail="Investigation worker is not running")
        followup_job_id = worker.enqueue(topic_id=topic_id, query=request.body)
    with session(settings) as conn:
        row = conn.execute("SELECT id FROM topics WHERE id = ?", (topic_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Unknown topic_id: {topic_id}")
        feedback_id = f"feedback-{uuid.uuid4().hex}"
        conn.execute(
            """
            INSERT INTO feedback_items (id, topic_id, body, create_followup_job, followup_job_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                feedback_id,
                topic_id,
                request.body,
                int(request.create_followup_job),
                followup_job_id,
            ),
        )
    return {"feedback_id": feedback_id, "followup_job_id": followup_job_id}


@app.post("/api/slice/run")
def run_slice(request: SliceRunRequest, settings: SettingsDep) -> dict[str, Any]:
    init_db(settings)
    import_result = import_objectives(settings=settings)
    try:
        if request.source_path:
            if request.source_in_inbox:
                ingest_result = ingest_inbox_file(
                    request.source_path,
                    objective_ids=[request.objective_id],
                    topic_ids=[request.topic_id] if request.topic_id else [],
                    settings=settings,
                )
            else:
                ingest_result = ingest_local_file(
                    Path(request.source_path),
                    objective_ids=[request.objective_id],
                    topic_ids=[request.topic_id] if request.topic_id else [],
                    settings=settings,
                )
        else:
            ingest_result = ingest_local_file(
                settings.bundled_study_guide_path,
                source_type="study_guide_pdf",
                objective_ids=[request.objective_id],
                topic_ids=[request.topic_id] if request.topic_id else [],
                settings=settings,
            )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rag_results = RagStore(settings).query(request.query, k=3, objective_id=request.objective_id)
    stub_payload = build_stub_codex_output(
        objective_id=request.objective_id,
        topic_id=request.topic_id,
        title=f"Study Slice for {request.objective_id}",
        retrieved_chunks=rag_results,
    )
    note_result = ingest_codex_output(stub_payload, settings)
    return {
        "objective_import": import_result,
        "ingest": ingest_result,
        "rag_results": rag_results,
        "codex_stub_ingest": note_result,
    }


@app.get("/api/provider/codex")
def codex_provider_info() -> dict[str, Any]:
    return CodexOperatorProvider().info().model_dump()


def _decode_quiz(row: Any) -> dict[str, Any]:
    data = dict(row)
    data["options"] = json.loads(data.pop("options_json"))
    data["metadata"] = json.loads(data.pop("metadata_json"))
    return data


def _decode_job(row: Any) -> dict[str, Any]:
    data = dict(row)
    data["logs"] = json.loads(data.pop("logs_json"))
    data["gaps"] = json.loads(data.pop("gaps_json"))
    data["artifact_ids"] = json.loads(data.pop("artifact_ids_json"))
    return data
