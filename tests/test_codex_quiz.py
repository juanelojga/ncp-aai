import pytest
from sqlalchemy import select

from ncp_aai.agents.codex_provider import CodexOutputInput
from ncp_aai.db import session
from ncp_aai.ingestion.service import ingest_inbox_file
from ncp_aai.models import SourceChunk
from ncp_aai.objectives import import_objectives
from ncp_aai.synthesis.notes import ingest_codex_output
from ncp_aai.synthesis.quizzes import grade_quiz_attempt


def _seed_chunk(app_settings) -> str:
    import_objectives(settings=app_settings)
    source = app_settings.app_inbox_dir / "react.txt"
    source.write_text(
        "ReAct alternates reasoning traces with actions and observations for agent workflows.",
        encoding="utf-8",
    )
    ingest_inbox_file("react.txt", objective_ids=["objective-1.2"], settings=app_settings)
    with session(app_settings) as db:
        chunk_id = db.scalar(select(SourceChunk.id).limit(1))
    assert chunk_id is not None
    return chunk_id


def test_codex_output_requires_real_citations_and_quiz_attempts_grade(app_settings):
    chunk_id = _seed_chunk(app_settings)
    payload = CodexOutputInput.model_validate(
        {
            "provider_metadata": {
                "provider": "codex",
                "model": "gpt-integrated",
                "prompt_version": "v1",
            },
            "objective_id": "objective-1.2",
            "title": "ReAct Frameworks",
            "note_body": "ReAct interleaves reasoning, actions, and observations.",
            "citations": [{"source_chunk_id": chunk_id, "label": "seed"}],
            "quiz_items": [
                {
                    "prompt": "What does ReAct interleave?",
                    "options": ["Reasoning and actions", "Only memory", "Only UI", "Only logging"],
                    "correct_option": 0,
                    "rationale": "The cited chunk describes reasoning, actions, and observations.",
                    "difficulty": "easy",
                    "concept": "ReAct",
                    "citations": [{"source_chunk_id": chunk_id}],
                }
            ],
        }
    )

    result = ingest_codex_output(payload, app_settings)
    assert result["citation_count"] == 2
    assert len(result["quiz_question_ids"]) == 1
    assert (app_settings.app_vault_dir).exists()

    attempt = grade_quiz_attempt(
        quiz_question_id=result["quiz_question_ids"][0],
        selected_option=0,
        settings=app_settings,
    )
    assert attempt["is_correct"] is True
    assert attempt["score"] == 1.0


def test_codex_output_rejects_missing_citation(app_settings):
    _seed_chunk(app_settings)
    payload = CodexOutputInput.model_validate(
        {
            "objective_id": "objective-1.2",
            "title": "Bad Citation",
            "note_body": "This should fail.",
            "citations": [{"source_chunk_id": "chunk-missing"}],
            "quiz_items": [],
        }
    )

    with pytest.raises(ValueError, match="Unresolved citation"):
        ingest_codex_output(payload, app_settings)
