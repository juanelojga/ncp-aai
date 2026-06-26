import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi import Path as ApiPath
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select, text

from ncp_aai import __version__
from ncp_aai.agents.codex_provider import CodexOperatorProvider, CodexOutputInput
from ncp_aai.agents.local_stub import build_stub_codex_output
from ncp_aai.config import Settings, get_settings
from ncp_aai.db import init_db, mapping_to_dict, model_to_dict, session
from ncp_aai.ingestion.service import ingest_inbox_file, ingest_local_file
from ncp_aai.jobs.investigation import (
    AmbiguousTopicError,
    InvestigationError,
    create_investigation_job,
    get_investigation_job,
    ingest_operator_output_for_job,
    run_local_investigation,
)
from ncp_aai.jobs.queue import InvestigationWorker
from ncp_aai.models import (
    AppSetting,
    Domain,
    ExerciseRecommendation,
    FeedbackItem,
    InvestigationJob,
    Note,
    Objective,
    QuizAttempt,
    QuizQuestion,
    SourceRecord,
    Topic,
    TopicSource,
)
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
WEB_DIST_DIR = Path(__file__).resolve().parents[1] / "web" / "dist"


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
    k: int = Field(default=5, ge=1, le=25)
    auto_ingest: bool = True


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
        with session(settings) as db:
            db.execute(text("SELECT 1")).fetchone()
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
    with session(settings) as db:
        domain_rows = db.scalars(select(Domain).order_by(Domain.number)).all()
        latest_quiz_score = (
            select(QuizAttempt.score)
            .where(QuizAttempt.objective_id == Objective.id)
            .order_by(desc(QuizAttempt.created_at))
            .limit(1)
            .scalar_subquery()
        )
        objective_rows = db.execute(
            select(
                Objective,
                Topic.id.label("topic_id"),
                func.count(func.distinct(TopicSource.source_id)).label("source_count"),
                func.count(func.distinct(Note.id)).label("note_count"),
                func.count(func.distinct(QuizQuestion.id)).label("quiz_count"),
                latest_quiz_score.label("latest_quiz_score"),
            )
            .outerjoin(Topic, Topic.objective_id == Objective.id)
            .outerjoin(TopicSource, TopicSource.topic_id == Topic.id)
            .outerjoin(Note, Note.objective_id == Objective.id)
            .outerjoin(QuizQuestion, QuizQuestion.objective_id == Objective.id)
            .group_by(Objective.id, Topic.id)
        ).all()
        settings_rows = db.scalars(select(AppSetting)).all()

    objectives_by_domain: dict[str, list[dict[str, Any]]] = {}
    for row in objective_rows:
        objective_model = row[0]
        objective = model_to_dict(objective_model)
        objective["topic_id"] = row.topic_id
        objective["source_count"] = int(row.source_count or 0)
        objective["note_count"] = int(row.note_count or 0)
        objective["quiz_count"] = int(row.quiz_count or 0)
        objective["latest_quiz_score"] = row.latest_quiz_score
        objectives_by_domain.setdefault(objective["domain_id"], []).append(objective)

    domains = []
    for row in domain_rows:
        domain = model_to_dict(row)
        domain["objectives"] = objectives_by_domain.get(domain["id"], [])
        domain["objectives"].sort(
            key=lambda item: tuple(int(part) for part in item["number"].split("."))
        )
        domains.append(domain)

    return {
        "domains": domains,
        "metadata": {row.key: json.loads(row.value) for row in settings_rows},
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
    with session(settings) as db:
        topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail=f"Unknown topic_id: {topic_id}")
    query = request.query or topic.title
    try:
        if request.codex_output:
            job_id = create_investigation_job(topic_id=topic_id, query=query, settings=settings)
            ingest_operator_output_for_job(job_id, request.codex_output, settings)
            return {"job_id": job_id, "status": "complete"}
        result = run_local_investigation(
            topic_id,
            query=query,
            k=request.k,
            auto_ingest=request.auto_ingest,
            settings=settings,
        )
        return {"job_id": result["job_id"], "status": result["status"]}
    except AmbiguousTopicError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvestigationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/investigations/{job_id}")
def get_investigation(job_id: Annotated[str, ApiPath()], settings: SettingsDep) -> dict[str, Any]:
    try:
        return get_investigation_job(job_id, settings)
    except InvestigationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/topics/{topic_id}")
def get_topic(topic_id: Annotated[str, ApiPath()], settings: SettingsDep) -> dict[str, Any]:
    with session(settings) as db:
        topic = db.execute(
            select(
                Topic.id,
                Topic.objective_id,
                Topic.title,
                Topic.status,
                Topic.created_at,
                Topic.updated_at,
                Objective.number.label("objective_number"),
                Objective.title.label("objective_title"),
                Domain.name.label("domain_name"),
            )
            .join(Objective, Objective.id == Topic.objective_id)
            .join(Domain, Domain.id == Objective.domain_id)
            .where(Topic.id == topic_id)
        ).first()
        if topic is None:
            raise HTTPException(status_code=404, detail=f"Unknown topic_id: {topic_id}")
        notes = db.scalars(
            select(Note).where(Note.topic_id == topic_id).order_by(desc(Note.created_at))
        ).all()
        sources = db.scalars(
            select(SourceRecord)
            .join(TopicSource, TopicSource.source_id == SourceRecord.id)
            .where(TopicSource.topic_id == topic_id)
            .order_by(desc(SourceRecord.created_at))
        ).all()
        quizzes = db.scalars(
            select(QuizQuestion)
            .where(QuizQuestion.topic_id == topic_id)
            .order_by(desc(QuizQuestion.created_at))
        ).all()
        exercises = db.scalars(
            select(ExerciseRecommendation)
            .where(ExerciseRecommendation.topic_id == topic_id)
            .order_by(desc(ExerciseRecommendation.created_at))
        ).all()
        feedback = db.scalars(
            select(FeedbackItem)
            .where(FeedbackItem.topic_id == topic_id)
            .order_by(desc(FeedbackItem.created_at))
        ).all()
        jobs = db.scalars(
            select(InvestigationJob)
            .where(InvestigationJob.topic_id == topic_id)
            .order_by(desc(InvestigationJob.created_at))
        ).all()
    return {
        "topic": mapping_to_dict(topic),
        "notes": [model_to_dict(row) for row in notes],
        "sources": [model_to_dict(row) for row in sources],
        "quiz_questions": [_decode_quiz(row) for row in quizzes],
        "exercises": [model_to_dict(row) for row in exercises],
        "feedback": [model_to_dict(row) for row in feedback],
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
    with session(settings) as db:
        if db.get(Topic, topic_id) is None:
            raise HTTPException(status_code=404, detail=f"Unknown topic_id: {topic_id}")
        feedback_id = f"feedback-{uuid.uuid4().hex}"
        db.add(
            FeedbackItem(
                id=feedback_id,
                topic_id=topic_id,
                body=request.body,
                create_followup_job=int(request.create_followup_job),
                followup_job_id=followup_job_id,
            )
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


@app.get("/assets/{asset_path:path}", include_in_schema=False)
def serve_web_asset(asset_path: str) -> FileResponse:
    asset = (WEB_DIST_DIR / "assets" / asset_path).resolve()
    assets_dir = (WEB_DIST_DIR / "assets").resolve()
    if not WEB_DIST_DIR.exists() or assets_dir not in asset.parents or not asset.is_file():
        raise HTTPException(status_code=404, detail="Web asset not found")
    return FileResponse(asset)


@app.get("/{spa_path:path}", include_in_schema=False)
def serve_spa(spa_path: str) -> FileResponse:
    if spa_path == "health" or spa_path.startswith(("api/", "admin/")):
        raise HTTPException(status_code=404, detail="API route not found")
    index = WEB_DIST_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Frontend build not found")
    return FileResponse(index)


def _decode_quiz(row: Any) -> dict[str, Any]:
    data = model_to_dict(row) if hasattr(row, "__table__") else mapping_to_dict(row)
    data["options"] = json.loads(data.pop("options_json"))
    data["metadata"] = json.loads(data.pop("metadata_json"))
    return data


def _decode_job(row: Any) -> dict[str, Any]:
    data = model_to_dict(row) if hasattr(row, "__table__") else mapping_to_dict(row)
    data["logs"] = json.loads(data.pop("logs_json"))
    data["gaps"] = json.loads(data.pop("gaps_json"))
    data["artifact_ids"] = json.loads(data.pop("artifact_ids_json"))
    return data
