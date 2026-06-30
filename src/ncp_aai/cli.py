import argparse
import json
import sys
import time
from pathlib import Path

from ncp_aai.agents.codex_bridge import (
    codex_response_path,
    ensure_bridge_directories,
    load_codex_response,
    request_dir,
    run_codex_for_request,
)
from ncp_aai.config import Settings, get_settings
from ncp_aai.db import init_db, session
from ncp_aai.ingestion.service import ingest_local_file
from ncp_aai.jobs.domain_generation import generate_domain_study_material
from ncp_aai.jobs.investigation import (
    AmbiguousTopicError,
    InvestigationError,
    _update_job,
    ingest_codex_payload_for_job,
    run_local_investigation,
)
from ncp_aai.models import InvestigationJob
from ncp_aai.objectives import import_objectives
from ncp_aai.rag.store import RagStore


def main() -> None:
    parser = argparse.ArgumentParser(prog="ncp-aai")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db")
    subparsers.add_parser("import-objectives")

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("path")
    ingest_parser.add_argument("--objective-id", action="append", default=[])
    ingest_parser.add_argument("--topic-id", action="append", default=[])

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("query")
    query_parser.add_argument("--k", type=int, default=5)

    investigate_parser = subparsers.add_parser("investigate")
    investigate_parser.add_argument("topic")
    investigate_parser.add_argument("--query")
    investigate_parser.add_argument("--k", type=int, default=5)
    investigate_parser.add_argument("--no-auto-ingest", action="store_true")
    investigate_parser.add_argument("--json", action="store_true")

    generate_domain_parser = subparsers.add_parser("generate-domain")
    generate_domain_parser.add_argument("domain")
    generate_domain_parser.add_argument(
        "--mode",
        choices=["host_codex", "local_stub"],
        default="host_codex",
    )
    generate_domain_parser.add_argument("--k", type=int, default=12)
    generate_domain_parser.add_argument("--no-auto-ingest", action="store_true")
    generate_domain_parser.add_argument("--force", action="store_true")
    generate_domain_parser.add_argument("--topic-id", action="append", default=[])

    codex_worker_parser = subparsers.add_parser("codex-worker")
    codex_worker_parser.add_argument("--once", action="store_true")
    codex_worker_parser.add_argument("--poll-seconds", type=float, default=2.0)
    codex_worker_parser.add_argument("--codex-binary", default="codex")

    args = parser.parse_args()
    settings = get_settings()
    init_db(settings)

    if args.command == "init-db":
        print(json.dumps({"status": "ok", "database": str(settings.sqlite_path)}, indent=2))
    elif args.command == "import-objectives":
        print(json.dumps(import_objectives(settings=settings), indent=2))
    elif args.command == "ingest":
        print(
            json.dumps(
                ingest_local_file(
                    Path(args.path),
                    objective_ids=args.objective_id,
                    topic_ids=args.topic_id,
                    settings=settings,
                ),
                indent=2,
            )
        )
    elif args.command == "query":
        print(json.dumps(RagStore(settings).query(args.query, k=args.k), indent=2))
    elif args.command == "investigate":
        try:
            print(
                json.dumps(
                    run_local_investigation(
                        args.topic,
                        query=args.query,
                        k=args.k,
                        auto_ingest=not args.no_auto_ingest,
                        settings=settings,
                    ),
                    indent=2,
                )
            )
        except AmbiguousTopicError as exc:
            parser.exit(2, json.dumps({"error": str(exc), "candidates": exc.candidates}) + "\n")
        except InvestigationError as exc:
            parser.exit(1, json.dumps({"error": str(exc)}) + "\n")
    elif args.command == "generate-domain":
        try:
            print(
                json.dumps(
                    generate_domain_study_material(
                        args.domain,
                        mode=args.mode,
                        k=args.k,
                        auto_ingest=not args.no_auto_ingest,
                        force=args.force,
                        topic_ids=args.topic_id,
                        settings=settings,
                    ),
                    indent=2,
                )
            )
        except ValueError as exc:
            parser.exit(1, json.dumps({"error": str(exc)}) + "\n")
    elif args.command == "codex-worker":
        _run_codex_worker(
            once=args.once,
            poll_seconds=args.poll_seconds,
            codex_binary=args.codex_binary,
        )


def _run_codex_worker(*, once: bool, poll_seconds: float, codex_binary: str) -> None:
    settings = get_settings()
    ensure_bridge_directories(settings)
    processed: set[Path] = set()
    while True:
        handled = False
        for request_path in sorted(request_dir(settings).glob("*.json")):
            if request_path in processed:
                continue
            job_id = request_path.stem
            if _job_is_complete(job_id, settings):
                processed.add(request_path)
                continue
            try:
                _process_codex_request(request_path, job_id, settings, codex_binary)
            except Exception as exc:  # noqa: BLE001 - one bad job must not stop the loop
                processed.add(request_path)
                _update_job(
                    job_id,
                    settings,
                    status="failed",
                    error=str(exc),
                    log=f"Codex worker failed to process request: {exc}",
                    complete=True,
                )
                print(
                    json.dumps(
                        {"job_id": job_id, "request_path": str(request_path), "error": str(exc)}
                    ),
                    file=sys.stderr,
                )
                continue
            processed.add(request_path)
            handled = True
        if once:
            return
        if not handled:
            time.sleep(poll_seconds)


def _process_codex_request(
    request_path: Path,
    job_id: str,
    settings: Settings,
    codex_binary: str,
) -> None:
    response_path = codex_response_path(job_id, settings)
    if not response_path.exists():
        response_path = run_codex_for_request(
            request_path,
            settings=settings,
            codex_binary=codex_binary,
        )
    payload = load_codex_response(job_id, settings)
    if payload is None:
        raise FileNotFoundError(f"No Codex response found at {response_path}")
    result = ingest_codex_payload_for_job(job_id, payload, settings)
    print(
        json.dumps(
            {
                "job_id": job_id,
                "request_path": str(request_path),
                "response_path": str(response_path),
                "note_id": result["note_id"],
                "quiz_question_ids": result["quiz_question_ids"],
            },
            indent=2,
        )
    )


def _job_is_complete(job_id: str, settings: Settings) -> bool:
    with session(settings) as db:
        job = db.get(InvestigationJob, job_id)
        status = job.status if job else None
    return status == "complete"
