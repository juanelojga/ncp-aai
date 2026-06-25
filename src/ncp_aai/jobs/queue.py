import json
import queue
import threading
import uuid
from typing import Any

from sqlalchemy import text, update

from ncp_aai.agents.codex_provider import CodexOutputInput
from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session
from ncp_aai.models import InvestigationJob
from ncp_aai.rag.store import RagStore
from ncp_aai.synthesis.notes import ingest_codex_output

TERMINAL_STATUSES = {"complete", "failed", "needs_review"}


class InvestigationWorker:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._payloads: dict[str, dict[str, Any]] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="investigation-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._queue.put("")
            self._thread.join(timeout=3)

    def enqueue(
        self,
        *,
        topic_id: str | None,
        query: str,
        codex_output: dict[str, Any] | None = None,
    ) -> str:
        job_id = f"job-{uuid.uuid4().hex}"
        with session(self.settings) as db:
            db.add(
                InvestigationJob(
                    id=job_id,
                    topic_id=topic_id,
                    status="queued",
                    query=query,
                    logs_json=json.dumps(["Queued investigation job."]),
                )
            )
        self._payloads[job_id] = {"query": query, "codex_output": codex_output}
        self._queue.put(job_id)
        return job_id

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job_id = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if not job_id:
                continue
            try:
                self._process(job_id, self._payloads.pop(job_id, {}))
            except Exception as exc:
                _update_job(
                    job_id,
                    self.settings,
                    status="failed",
                    error=str(exc),
                    log=f"Job failed: {exc}",
                    complete=True,
                )

    def _process(self, job_id: str, payload: dict[str, Any]) -> None:
        with session(self.settings) as db:
            job = db.get(InvestigationJob, job_id)
        if job is None:
            return

        query = payload.get("query") or job.query or ""
        _update_job(job_id, self.settings, status="collecting_sources", log="Querying local RAG.")
        results = RagStore(self.settings).query(query, k=5, topic_id=job.topic_id)
        _update_job(
            job_id,
            self.settings,
            status="extracting",
            log=f"Retrieved {len(results)} local chunks.",
        )
        _update_job(job_id, self.settings, status="synthesizing", log="Checking operator output.")

        if payload.get("codex_output"):
            codex_payload = CodexOutputInput.model_validate(payload["codex_output"])
            result = ingest_codex_output(codex_payload, self.settings)
            _update_job(
                job_id,
                self.settings,
                status="complete",
                log="Validated and persisted operator-provided Codex output.",
                artifacts=[result["note_id"], *result["quiz_question_ids"]],
                complete=True,
            )
            return

        _update_job(
            job_id,
            self.settings,
            status="needs_review",
            log="Local retrieval complete; submit Codex output to finish synthesis.",
            gaps=["Operator Codex output is required for synthesized notes/quizzes."],
            complete=True,
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

        if complete:
            db.execute(
                update(InvestigationJob)
                .where(InvestigationJob.id == job_id)
                .values(
                    status=status,
                    logs_json=json.dumps(logs),
                    gaps_json=json.dumps(current_gaps),
                    artifact_ids_json=json.dumps(current_artifacts),
                    error=error,
                    updated_at=text("CURRENT_TIMESTAMP"),
                    completed_at=text("CURRENT_TIMESTAMP"),
                )
            )
        else:
            db.execute(
                update(InvestigationJob)
                .where(InvestigationJob.id == job_id)
                .values(
                    status=status,
                    logs_json=json.dumps(logs),
                    gaps_json=json.dumps(current_gaps),
                    artifact_ids_json=json.dumps(current_artifacts),
                    error=error,
                    updated_at=text("CURRENT_TIMESTAMP"),
                    started_at=text("COALESCE(started_at, CURRENT_TIMESTAMP)"),
                )
            )
