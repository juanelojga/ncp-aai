from fastapi.testclient import TestClient
from sqlalchemy import func, select

import ncp_aai.cli as cli_module
from ncp_aai.db import session
from ncp_aai.jobs.suggested_readings import (
    FetchedPage,
    ResolvedPage,
    fetch_suggested_readings,
    parse_reading_seeds,
)
from ncp_aai.main import app, settings_dep
from ncp_aai.models import SourceChunk, SourceRecord, TopicSource, VectorEntry
from ncp_aai.objectives import import_objectives


class StaticResolver:
    def resolve(self, seed):
        return ResolvedPage(
            url=f"https://example.test/{seed.domain_id}/{seed.title.lower().replace(' ', '-')}",
            title=seed.title,
        )


class StaticFetcher:
    def fetch(self, page):
        text = (
            f"{page.title} explains agentic AI study concepts with NVIDIA platform context. "
            "It covers architecture, orchestration, communication, memory, retrieval, "
            "evaluation, deployment, monitoring, guardrails, and human oversight. "
        ) * 4
        return FetchedPage(
            url=page.url,
            title=page.title or "Suggested Reading",
            text=text,
            content_type="text/html",
        )


class FailingFirstFetcher:
    def __init__(self):
        self.calls = 0

    def fetch(self, page):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("mock fetch failure")
        return StaticFetcher().fetch(page)


def test_parse_reading_seeds_extracts_courses_and_readings(app_settings):
    seeds = parse_reading_seeds(settings=app_settings)

    domain_one = [seed for seed in seeds if seed.domain_id == "domain-1"]
    assert len(domain_one) == 6
    assert domain_one[0].title == "Agentic AI in the Factory"
    assert domain_one[0].courses == ("Building Agentic AI Applications with LLMs",)
    assert any(seed.title == "What Are Multi-Agent Systems?" for seed in domain_one)


def test_domain_readings_map_to_all_domain_topics(app_settings):
    import_objectives(settings=app_settings)

    result = fetch_suggested_readings(
        domain_id="domain-1",
        limit=1,
        dry_run=True,
        settings=app_settings,
    )

    assert result["counts"] == {"skipped": 1}
    assert result["results"][0]["topic_ids"] == [f"topic-1.{index}" for index in range(1, 9)]


def test_fetch_creates_source_chunks_topic_links_and_vectors(app_settings):
    import_objectives(settings=app_settings)

    result = fetch_suggested_readings(
        domain_id="domain-1",
        limit=1,
        resolver=StaticResolver(),
        fetcher=StaticFetcher(),
        settings=app_settings,
    )

    assert result["counts"] == {"fetched": 1}
    source_id = result["results"][0]["source_id"]
    with session(app_settings) as db:
        source = db.get(SourceRecord, source_id)
        chunk_count = db.scalar(
            select(func.count()).select_from(SourceChunk).where(SourceChunk.source_id == source_id)
        )
        vector_count = db.scalar(
            select(func.count())
            .select_from(VectorEntry)
            .join(SourceChunk, SourceChunk.id == VectorEntry.source_chunk_id)
            .where(SourceChunk.source_id == source_id)
        )
        topic_link_count = db.scalar(
            select(func.count()).select_from(TopicSource).where(TopicSource.source_id == source_id)
        )

    assert source is not None
    assert source.source_type == "suggested_reading"
    assert source.url.startswith("https://example.test/domain-1/")
    assert chunk_count >= 1
    assert vector_count == chunk_count
    assert topic_link_count == 8


def test_fetch_is_idempotent_by_url_and_topic_links(app_settings):
    import_objectives(settings=app_settings)

    first = fetch_suggested_readings(
        domain_id="domain-1",
        limit=1,
        resolver=StaticResolver(),
        fetcher=StaticFetcher(),
        settings=app_settings,
    )
    second = fetch_suggested_readings(
        domain_id="domain-1",
        limit=1,
        resolver=StaticResolver(),
        fetcher=StaticFetcher(),
        settings=app_settings,
    )

    source_id = first["results"][0]["source_id"]
    assert second["counts"] == {"linked": 1}
    assert second["results"][0]["source_id"] == source_id
    with session(app_settings) as db:
        source_count = db.scalar(select(func.count()).select_from(SourceRecord))
        topic_link_count = db.scalar(
            select(func.count()).select_from(TopicSource).where(TopicSource.source_id == source_id)
        )
    assert source_count == 1
    assert topic_link_count == 8


def test_api_dry_run_returns_plan_without_creating_sources(app_settings):
    import_objectives(settings=app_settings)
    app.dependency_overrides[settings_dep] = lambda: app_settings
    try:
        client = TestClient(app)
        response = client.post(
            "/api/readings/fetch",
            json={"domain_id": "domain-1", "limit": 2, "dry_run": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["counts"] == {"skipped": 2}
    with session(app_settings) as db:
        source_count = db.scalar(select(func.count()).select_from(SourceRecord))
    assert source_count == 0


def test_cli_dry_run_outputs_planned_readings(app_settings, monkeypatch, capsys):
    import_objectives(settings=app_settings)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ncp-aai",
            "fetch-readings",
            "--domain",
            "domain-1",
            "--limit",
            "1",
            "--dry-run",
            "--json",
        ],
    )

    cli_module.main()

    captured = capsys.readouterr()
    assert '"dry_run": true' in captured.out
    assert "Agentic AI in the Factory" in captured.out


def test_fetch_failure_is_reported_while_other_readings_continue(app_settings):
    import_objectives(settings=app_settings)

    result = fetch_suggested_readings(
        domain_id="domain-1",
        limit=2,
        resolver=StaticResolver(),
        fetcher=FailingFirstFetcher(),
        settings=app_settings,
    )

    assert result["counts"] == {"failed": 1, "fetched": 1}
    assert result["results"][0]["status"] == "failed"
    assert "mock fetch failure" in result["results"][0]["error"]
    assert result["results"][1]["status"] == "fetched"
