import json
import sys

import pytest

from ncp_aai.cli import main as cli_main
from ncp_aai.db import session
from ncp_aai.ingestion.service import ingest_inbox_file, ingest_local_file
from ncp_aai.jobs import investigation as investigation_module
from ncp_aai.jobs.investigation import (
    SourceUnavailableError,
    resolve_topic,
    run_local_investigation,
)
from ncp_aai.models import InvestigationJob, Note, QuizQuestion
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
