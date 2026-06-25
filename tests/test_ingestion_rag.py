from sqlalchemy import func, select

from ncp_aai.db import session
from ncp_aai.ingestion.service import ingest_inbox_file
from ncp_aai.models import SourceRecord
from ncp_aai.objectives import import_objectives
from ncp_aai.rag.store import RagStore


def test_markdown_ingest_deduplicates_and_queries(app_settings):
    import_objectives(settings=app_settings)
    source = app_settings.app_inbox_dir / "rag.md"
    source.write_text(
        "# Retrieval Pipelines\n\n"
        "RAG systems embed chunks and retrieve relevant context for grounded answers.\n"
        "Vector databases support fast semantic search over local study material.\n",
        encoding="utf-8",
    )

    first = ingest_inbox_file(
        "rag.md",
        objective_ids=["objective-6.1"],
        settings=app_settings,
    )
    second = ingest_inbox_file(
        "rag.md",
        objective_ids=["objective-6.1"],
        settings=app_settings,
    )

    assert first["deduplicated"] is False
    assert second["deduplicated"] is True
    assert first["source_id"] == second["source_id"]
    assert first["chunk_count"] >= 1
    assert first["vector_count"] == first["chunk_count"]

    results = RagStore(app_settings).query("semantic retrieval with vector databases", k=3)
    assert results
    assert results[0]["chunk_id"].startswith("chunk-")
    assert "Vector databases" in results[0]["text"]

    with session(app_settings) as db:
        source_count = db.scalar(select(func.count()).select_from(SourceRecord))
    assert source_count == 1
