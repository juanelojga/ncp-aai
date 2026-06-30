import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session
from ncp_aai.ingestion.normalize import normalize_text
from ncp_aai.ingestion.service import ingest_text_source
from ncp_aai.models import Domain, Objective, SourceRecord, Topic, TopicSource

DOMAIN_RE = re.compile(r"^## Domain (?P<number>\d+) [—-] (?P<name>.+?) \((?P<weight>\d+)%\)")
COURSES_RE = re.compile(r"^- \*\*Courses?:\*\* (?P<value>.+)$")
READINGS_RE = re.compile(r"^- \*\*Seed readings:\*\* (?P<value>.+)$")


@dataclass(frozen=True)
class ReadingSeed:
    domain_id: str
    domain_number: int
    domain_name: str
    title: str
    courses: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedPage:
    url: str
    title: str | None = None


@dataclass(frozen=True)
class FetchedPage:
    url: str
    title: str
    text: str
    content_type: str


def parse_reading_seeds(
    path: str | None = None, settings: Settings | None = None
) -> list[ReadingSeed]:
    settings = settings or get_settings()
    objectives_path = (
        settings.project_root / "EXAM_OBJECTIVES.md"
        if path is None
        else settings.project_root / path
    )
    current_domain: dict[str, Any] | None = None
    courses: tuple[str, ...] = ()
    seeds: list[ReadingSeed] = []

    for raw_line in objectives_path.read_text(encoding="utf-8").splitlines():
        if domain_match := DOMAIN_RE.match(raw_line):
            number = int(domain_match.group("number"))
            current_domain = {
                "id": f"domain-{number}",
                "number": number,
                "name": domain_match.group("name").strip(),
            }
            courses = ()
            continue
        if current_domain is None:
            continue
        if courses_match := COURSES_RE.match(raw_line):
            courses = tuple(_split_seed_items(courses_match.group("value")))
            continue
        if readings_match := READINGS_RE.match(raw_line):
            seeds.extend(
                ReadingSeed(
                    domain_id=current_domain["id"],
                    domain_number=current_domain["number"],
                    domain_name=current_domain["name"],
                    title=title,
                    courses=courses,
                )
                for title in _split_seed_items(readings_match.group("value"))
            )

    return seeds


def fetch_suggested_readings(
    *,
    domain_id: str | None = None,
    topic_id: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    force: bool = False,
    settings: Settings | None = None,
    resolver: Any | None = None,
    fetcher: Any | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    resolver = resolver or DuckDuckGoResolver()
    fetcher = fetcher or HtmlFetcher()

    seeds = parse_reading_seeds(settings=settings)
    if domain_id:
        _ensure_domain_exists(domain_id, settings)
        seeds = [seed for seed in seeds if seed.domain_id == domain_id]
    if topic_id:
        topic_domain_id = _domain_for_topic(topic_id, settings)
        if domain_id and topic_domain_id != domain_id:
            msg = f"{topic_id} does not belong to {domain_id}"
            raise ValueError(msg)
        seeds = [seed for seed in seeds if seed.domain_id == topic_domain_id]
    if limit is not None:
        seeds = seeds[:limit]

    planned = []
    for seed in seeds:
        topic_ids = [topic_id] if topic_id else _topic_ids_for_domain(seed.domain_id, settings)
        planned.append((seed, topic_ids))

    if dry_run:
        results = [
            _result(
                seed,
                status="skipped",
                topic_ids=topic_ids,
                message="dry_run",
            )
            for seed, topic_ids in planned
        ]
        return _summarize(results, dry_run=True)

    results: list[dict[str, Any]] = []
    for seed, topic_ids in planned:
        try:
            results.append(
                _fetch_one_reading(
                    seed,
                    topic_ids=topic_ids,
                    force=force,
                    resolver=resolver,
                    fetcher=fetcher,
                    settings=settings,
                )
            )
        except Exception as exc:  # noqa: BLE001 - isolate each reading failure
            results.append(_result(seed, status="failed", topic_ids=topic_ids, error=str(exc)))

    return _summarize(results, dry_run=False)


class DuckDuckGoResolver:
    def __init__(self, timeout_seconds: float = 15.0) -> None:
        self.timeout_seconds = timeout_seconds

    def resolve(self, seed: ReadingSeed) -> ResolvedPage:
        query = f"{seed.title} {seed.domain_name}"
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        headers = {"User-Agent": "ncp-aai-study-fetcher/0.1"}
        with httpx.Client(
            timeout=self.timeout_seconds, follow_redirects=True, headers=headers
        ) as client:
            response = client.get(url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        candidates = []
        for link in soup.select("a.result__a"):
            href = link.get("href")
            title = normalize_text(link.get_text(" "))
            if not href:
                continue
            candidates.append(ResolvedPage(url=str(href), title=title or None))
        if not candidates:
            msg = f"No search result found for {seed.title}"
            raise RuntimeError(msg)
        return _choose_best_candidate(seed, candidates)


class HtmlFetcher:
    def __init__(self, timeout_seconds: float = 20.0) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(self, page: ResolvedPage) -> FetchedPage:
        headers = {"User-Agent": "ncp-aai-study-fetcher/0.1"}
        with httpx.Client(
            timeout=self.timeout_seconds, follow_redirects=True, headers=headers
        ) as client:
            response = client.get(page.url)
            response.raise_for_status()
        content_type = response.headers.get("content-type", "text/html").split(";")[0].strip()
        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(["script", "style", "noscript", "nav", "footer", "header", "form"]):
            element.decompose()
        title = (
            page.title
            or (soup.title.string.strip() if soup.title and soup.title.string else "")
            or page.url
        )
        main = soup.find("main") or soup.find("article") or soup.body or soup
        text = normalize_text(main.get_text("\n"))
        if len(text) < 200:
            msg = f"Fetched page did not contain enough readable text: {page.url}"
            raise RuntimeError(msg)
        return FetchedPage(url=str(response.url), title=title, text=text, content_type=content_type)


def _fetch_one_reading(
    seed: ReadingSeed,
    *,
    topic_ids: list[str],
    force: bool,
    resolver: Any,
    fetcher: Any,
    settings: Settings,
) -> dict[str, Any]:
    page = resolver.resolve(seed)
    existing_id = _source_id_for_url(page.url, settings)
    if existing_id and not force:
        _link_topics(existing_id, topic_ids, settings)
        return _result(
            seed,
            status="linked",
            topic_ids=topic_ids,
            url=page.url,
            source_id=existing_id,
            message="existing source reused",
        )

    fetched = fetcher.fetch(page)
    ingest_result = ingest_text_source(
        title=fetched.title or seed.title,
        text=fetched.text,
        source_type="suggested_reading",
        content_type=fetched.content_type,
        url=fetched.url,
        topic_ids=topic_ids,
        metadata={
            "seed_title": seed.title,
            "seed_domain_id": seed.domain_id,
            "seed_domain_name": seed.domain_name,
            "courses": list(seed.courses),
        },
        settings=settings,
    )
    return _result(
        seed,
        status="fetched",
        topic_ids=topic_ids,
        url=fetched.url,
        source_id=ingest_result["source_id"],
        chunk_count=ingest_result["chunk_count"],
        vector_count=ingest_result["vector_count"],
        deduplicated=ingest_result["deduplicated"],
    )


def _ensure_domain_exists(domain_id: str, settings: Settings) -> None:
    with session(settings) as db:
        exists = db.scalar(select(Domain.id).where(Domain.id == domain_id))
    if not exists:
        msg = f"Unknown domain_id: {domain_id}"
        raise ValueError(msg)


def _domain_for_topic(topic_id: str, settings: Settings) -> str:
    with session(settings) as db:
        domain_id = db.scalar(
            select(Objective.domain_id)
            .join(Topic, Topic.objective_id == Objective.id)
            .where(Topic.id == topic_id)
        )
    if domain_id is None:
        msg = f"Unknown topic_id: {topic_id}"
        raise ValueError(msg)
    return domain_id


def _topic_ids_for_domain(domain_id: str, settings: Settings) -> list[str]:
    with session(settings) as db:
        rows = db.scalars(
            select(Topic.id)
            .join(Objective, Objective.id == Topic.objective_id)
            .where(Objective.domain_id == domain_id)
            .order_by(Objective.number)
        ).all()
    return list(rows)


def _source_id_for_url(url: str, settings: Settings) -> str | None:
    with session(settings) as db:
        return db.scalar(select(SourceRecord.id).where(SourceRecord.url == url))


def _link_topics(source_id: str, topic_ids: list[str], settings: Settings) -> None:
    with session(settings) as db:
        for topic in topic_ids:
            db.execute(
                sqlite_insert(TopicSource)
                .values(topic_id=topic, source_id=source_id)
                .on_conflict_do_nothing()
            )


def _split_seed_items(value: str) -> list[str]:
    return [item.strip() for item in value.split(" · ") if item.strip()]


def _choose_best_candidate(seed: ReadingSeed, candidates: list[ResolvedPage]) -> ResolvedPage:
    preferred = ("nvidia.com", "developer.nvidia.com", "docs.nvidia.com", "github.com")
    seed_terms = _terms(seed.title)
    scored = []
    for index, candidate in enumerate(candidates):
        host = urlparse(candidate.url).netloc.lower()
        title_terms = _terms(candidate.title or "")
        score = len(seed_terms & title_terms)
        if any(domain in host for domain in preferred):
            score += 5
        scored.append((score, -index, candidate))
    scored.sort(reverse=True)
    return scored[0][2]


def _terms(value: str) -> set[str]:
    return {term for term in re.findall(r"[a-z0-9]+", value.lower()) if len(term) > 2}


def _result(
    seed: ReadingSeed,
    *,
    status: str,
    topic_ids: list[str],
    url: str | None = None,
    source_id: str | None = None,
    chunk_count: int = 0,
    vector_count: int = 0,
    deduplicated: bool = False,
    message: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "domain_id": seed.domain_id,
        "title": seed.title,
        "courses": list(seed.courses),
        "topic_ids": topic_ids,
        "status": status,
        "url": url,
        "source_id": source_id,
        "chunk_count": chunk_count,
        "vector_count": vector_count,
        "deduplicated": deduplicated,
        "message": message,
        "error": error,
    }


def _summarize(results: list[dict[str, Any]], *, dry_run: bool) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {
        "dry_run": dry_run,
        "counts": counts,
        "results": results,
    }
