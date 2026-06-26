import queue
import threading
from typing import Any

from sqlalchemy import select

from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session
from ncp_aai.jobs.investigation import (
    create_investigation_job,
    ingest_operator_output_for_job,
    run_local_investigation,
)
from ncp_aai.models import InvestigationJob


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
        job_id = create_investigation_job(topic_id=topic_id, query=query, settings=self.settings)
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
                # Shared investigation helpers already mark failed jobs before re-raising.
                print(f"Investigation job {job_id} failed: {exc}")

    def _process(self, job_id: str, payload: dict[str, Any]) -> None:
        topic_id = self._topic_id_for_job(job_id)
        if topic_id is None:
            return

        if payload.get("codex_output"):
            ingest_operator_output_for_job(job_id, payload["codex_output"], self.settings)
            return

        run_local_investigation(
            topic_id,
            query=payload.get("query"),
            settings=self.settings,
            job_id=job_id,
        )

    def _topic_id_for_job(self, job_id: str) -> str | None:
        with session(self.settings) as db:
            return db.scalar(
                select(InvestigationJob.topic_id).where(InvestigationJob.id == job_id)
            )
