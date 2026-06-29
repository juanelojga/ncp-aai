import json
import sys

import pytest
from sqlalchemy import select

from ncp_aai.cli import _run_codex_worker
from ncp_aai.cli import main as cli_main
from ncp_aai.db import session
from ncp_aai.ingestion.service import ingest_inbox_file, ingest_local_file
from ncp_aai.jobs import investigation as investigation_module
from ncp_aai.jobs.investigation import (
    SourceUnavailableError,
    ingest_codex_payload_for_job,
    resolve_topic,
    run_host_codex_investigation,
    run_local_investigation,
)
from ncp_aai.models import InvestigationJob, Note, QuizQuestion, SourceChunk
from ncp_aai.objectives import import_objectives


def _seed_ui_source(app_settings) -> None:
    import_objectives(settings=app_settings)
    source = app_settings.app_inbox_dir / "human-agent-ui.txt"
    source.write_text(
        "Human-agent interfaces should show agent state, invite user feedback, "
        "and keep control points clear for oversight.",
        encoding="utf-8",
    )
    ingest_inbox_file(
        "human-agent-ui.txt",
        objective_ids=["objective-1.1"],
        topic_ids=["topic-1.1"],
        settings=app_settings,
    )


def test_resolve_topic_accepts_id_and_title(app_settings):
    import_objectives(settings=app_settings)

    by_id = resolve_topic("topic-1.1", app_settings)
    by_title = resolve_topic(
        "Design user interfaces for intuitive human-agent interaction",
        app_settings,
    )

    assert by_id.id == "topic-1.1"
    assert by_title.id == "topic-1.1"
    assert by_title.objective_id == "objective-1.1"


def test_local_investigation_completes_and_persists_artifacts(app_settings):
    _seed_ui_source(app_settings)

    result = run_local_investigation(
        "Design user interfaces for intuitive human-agent interaction",
        settings=app_settings,
        auto_ingest=False,
    )

    assert result["status"] == "complete"
    assert result["topic_id"] == "topic-1.1"
    assert result["note_id"].startswith("note-")
    assert len(result["quiz_question_ids"]) == 1
    assert result["retrieved_chunk_count"] >= 1
    assert (app_settings.app_vault_dir / result["vault_path"].split("/")[-1]).exists()

    with session(app_settings) as db:
        job = db.get(InvestigationJob, result["job_id"])
        note = db.get(Note, result["note_id"])
        quiz = db.get(QuizQuestion, result["quiz_question_ids"][0])

    assert job is not None
    assert job.status == "complete"
    assert note is not None
    assert note.topic_id == "topic-1.1"
    assert quiz is not None
    assert quiz.topic_id == "topic-1.1"


def test_local_investigation_no_auto_ingest_fails_without_sources(app_settings):
    import_objectives(settings=app_settings)

    with pytest.raises(SourceUnavailableError, match="No indexed source chunks"):
        run_local_investigation("topic-1.1", settings=app_settings, auto_ingest=False)


def test_local_investigation_auto_ingests_when_sources_are_missing(
    app_settings, tmp_path, monkeypatch
):
    import_objectives(settings=app_settings)
    guide = tmp_path / "guide.md"
    guide.write_text(
        "# Human-Agent Interaction\n\n"
        "Intuitive human-agent interfaces expose agent intent, feedback affordances, "
        "and oversight checkpoints.",
        encoding="utf-8",
    )

    def ingest_test_guide(_path, **kwargs):
        return ingest_local_file(guide, **kwargs)

    monkeypatch.setattr(investigation_module, "ingest_local_file", ingest_test_guide)

    result = run_local_investigation("topic-1.1", settings=app_settings)

    assert result["status"] == "complete"
    assert result["ingest"]["chunk_count"] >= 1
    assert result["artifact_ids"]


def test_host_codex_investigation_writes_request_and_needs_review(app_settings):
    _seed_ui_source(app_settings)

    result = run_host_codex_investigation("topic-1.1", settings=app_settings, auto_ingest=False)

    assert result["status"] == "needs_review"
    request_path = app_settings.codex_output_dir / "requests" / f"{result['job_id']}.json"
    assert request_path.exists()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["topic_id"] == "topic-1.1"
    assert request["objective_id"] == "objective-1.1"
    assert len(request["retrieved_chunks"]) >= 1
    assert request["retrieved_chunks"][0]["source_chunk_id"]


def test_host_codex_response_ingests_new_note_version(app_settings):
    _seed_ui_source(app_settings)
    first = run_local_investigation("topic-1.1", settings=app_settings, auto_ingest=False)
    host = run_host_codex_investigation("topic-1.1", settings=app_settings, auto_ingest=False)
    with session(app_settings) as db:
        chunk_id = db.scalars(select(SourceChunk.id)).first()

    payload = {
        "provider_metadata": {"provider": "codex", "model": "gpt-host", "run_id": "run-host"},
        "objective_id": "objective-1.1",
        "topic_id": "topic-1.1",
        "title": "Host Codex Study Note",
        "note_body": "## Host synthesis\n\nHuman-agent interfaces expose status and feedback.",
        "citations": [
            {
                "source_chunk_id": chunk_id,
                "label": "Local chunk",
                "quote": "Human-agent interfaces should show agent state",
            }
        ],
        "quiz_items": [
            {
                "prompt": "What should human-agent interfaces expose?",
                "options": ["Agent state", "Only color", "Hidden tools", "No feedback"],
                "correct_option": 0,
                "rationale": "The cited source emphasizes visible state and feedback.",
                "difficulty": "easy",
                "concept": "Human-agent interaction",
                "citations": [{"source_chunk_id": chunk_id}],
            }
        ],
        "gaps": [],
    }
    response_path = app_settings.codex_output_dir / "responses" / f"{host['job_id']}.json"
    response_path.write_text(json.dumps(payload), encoding="utf-8")

    result = ingest_codex_payload_for_job(
        host["job_id"],
        investigation_module.load_codex_response(host["job_id"], app_settings),
        app_settings,
    )

    assert result["note_id"] != first["note_id"]
    with session(app_settings) as db:
        notes = db.scalars(select(Note.id)).all()
        job = db.get(InvestigationJob, host["job_id"])
    assert first["note_id"] in notes
    assert result["note_id"] in notes
    assert job.status == "complete"


def test_codex_worker_survives_a_bad_response(app_settings):
    _seed_ui_source(app_settings)
    bad = run_host_codex_investigation("topic-1.1", settings=app_settings, auto_ingest=False)
    good = run_host_codex_investigation("topic-1.1", settings=app_settings, auto_ingest=False)
    with session(app_settings) as db:
        chunk_id = db.scalars(select(SourceChunk.id)).first()

    responses_dir = app_settings.codex_output_dir / "responses"
    # Malformed JSON for the first job must not stop the worker from finishing the second.
    (responses_dir / f"{bad['job_id']}.json").write_text("{not valid json", encoding="utf-8")
    (responses_dir / f"{good['job_id']}.json").write_text(
        json.dumps(
            {
                "provider_metadata": {
                    "provider": "codex",
                    "model": "gpt-host",
                    "run_id": "run-good",
                },
                "objective_id": "objective-1.1",
                "topic_id": "topic-1.1",
                "title": "Good Host Note",
                "note_body": "## Synthesis\n\nHuman-agent interfaces expose status and feedback.",
                "citations": [{"source_chunk_id": chunk_id, "label": "Local chunk"}],
                "quiz_items": [],
                "gaps": [],
            }
        ),
        encoding="utf-8",
    )

    _run_codex_worker(once=True, poll_seconds=0.0, codex_binary="codex")

    with session(app_settings) as db:
        bad_job = db.get(InvestigationJob, bad["job_id"])
        good_job = db.get(InvestigationJob, good["job_id"])
    assert bad_job.status == "failed"
    assert bad_job.error
    assert good_job.status == "complete"


def test_cli_investigate_prints_json_result(app_settings, monkeypatch, capsys):
    _seed_ui_source(app_settings)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ncp-aai",
            "investigate",
            "Design user interfaces for intuitive human-agent interaction",
            "--no-auto-ingest",
        ],
    )

    cli_main()
    output = json.loads(capsys.readouterr().out)

    assert output["status"] == "complete"
    assert output["topic_id"] == "topic-1.1"
    assert output["note_id"].startswith("note-")
