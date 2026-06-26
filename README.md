# NCP-AAI Agentic Study Platform

A local-first study and investigation platform for preparing for the NVIDIA NCP-AAI certification.

The goal is to build a single-user web app that can investigate each exam topic in parts, collect source material from PDFs, official docs, YouTube transcripts, web pages, GitHub, and local notes, then turn that material into grounded study notes, quizzes, exercises, and readiness tracking.

## Current Status

The first backend implementation is in place. The repository now includes a FastAPI application,
SQLite persistence, objective import, local document ingestion, deterministic offline retrieval,
Codex-output ingestion, quiz attempts, feedback, background investigation jobs, Docker packaging,
the first React/Vite study web app, and focused backend/frontend test suites.

The product source of truth remains:

- [`PRD.md`](./PRD.md) - product requirements and architecture.
- [`plan/feature-agentic-study-platform-1.md`](./plan/feature-agentic-study-platform-1.md) - MVP implementation plan.
- [`EXAM_OBJECTIVES.md`](./EXAM_OBJECTIVES.md) - exam domain and objective tracker.
- [`SPECS.md`](./SPECS.md) - original concept document.

## MVP Decisions

The first implementation is intentionally scoped to a local, single-container setup.

| Area | Decision |
|---|---|
| Primary UI | React/Vite web app |
| Backend | FastAPI |
| Database | SQLite |
| Vector store | ChromaDB |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| First investigation provider | Codex |
| Deployment | One Docker container |
| Data persistence | Host bind mounts |

Lavish is no longer the primary study UI. It remains optional later for generated rich artifacts or exports.

The backend declares ChromaDB and sentence-transformers as runtime dependencies. For offline
development and tests, it falls back to a deterministic SQLite-backed vector store and hash
embeddings when those optional packages are not installed yet.

## Product Shape

The platform has two core systems.

### Investigation Engine

The investigation engine researches one topic, sub-objective, or free-form prompt at a time. It should work incrementally instead of trying to collect every possible source in one run.

Planned capabilities:

- Query the local knowledge base before external research.
- Collect source material from official NVIDIA docs, PDFs, YouTube transcripts, GitHub, public web pages, and local files.
- Store source metadata, extraction status, hashes, and provenance.
- Parse and chunk source content for retrieval.
- Generate cited notes, diagrams, quizzes, and exercises.
- Track unresolved gaps for later investigation passes.
- Support Codex first, with adapter boundaries for Claude, OpenAI-compatible APIs, Hermes, and local models later.

### Study Web App

The web app is the main daily study surface.

Planned screens:

- Dashboard for readiness, weak areas, active jobs, and recent activity.
- Objectives browser based on `EXAM_OBJECTIVES.md`.
- Topic detail pages with notes, citations, sources, quizzes, exercises, and job history.
- Investigation console for starting, inspecting, retrying, and resuming jobs.
- Source library for PDFs, web pages, transcripts, and extracted chunks.
- Study chat grounded in the local RAG database.
- Quiz and exercise flows with saved attempts and feedback.
- Settings for persistence paths, model/provider status, and API configuration.

## Persistence Model

All study data must survive container deletion and rebuilds.

The container will write persistent data only to mounted host directories:

| Host path | Container path | Purpose |
|---|---|---|
| `./data` | `/app/data` | SQLite database, ChromaDB, job state, settings, logs |
| `./vault` | `/app/vault` | Generated Markdown notes and optional Obsidian-compatible files |
| `./inbox` | `/app/inbox` | PDFs, Markdown, HTML, text, and user-dropped source files |
| `./artifacts` | `/app/artifacts` | Generated HTML, diagrams, exports, reports |

If the Docker container is removed, these host directories should remain. Deleting these directories deletes the study data.

## Run With Docker Compose

Docker Compose is the primary local run path. It builds the single-container runtime from
[`Dockerfile`](./Dockerfile), serves the bundled React app through FastAPI, and persists local
study data through bind mounts.

Create a local environment file and data directories:

```bash
cp .env.example .env
mkdir -p data vault inbox artifacts
```

Build and start the app:

```bash
docker compose up --build
```

The app should then be available at:

```text
http://localhost:48673/
http://localhost:48673/health
```

Set `APP_HOST_PORT` to override the Docker host port, for example
`APP_HOST_PORT=49157 docker compose up --build`.

Useful Compose commands:

```bash
docker compose config
docker compose ps
docker compose logs -f app
docker compose down
```

This project uses host bind mounts instead of Docker named volumes. `docker compose down` stops and
removes the container, but it keeps `./data`, `./vault`, `./inbox`, and `./artifacts`. To reset local
state, stop Compose and delete those directories:

```bash
docker compose down
rm -rf data vault inbox artifacts
mkdir -p data vault inbox artifacts
```

Seed the objective database:

```bash
curl -X POST http://localhost:48673/admin/import-objectives
```

Run the bundled study slice:

```bash
curl -X POST http://localhost:48673/api/slice/run \
  -H "Content-Type: application/json" \
  -d '{}'
```

For the complete runbook, including inbox ingestion, RAG queries, logs, and troubleshooting, see
[`docs/RUNNING.md`](./docs/RUNNING.md).

## Local Development

Install the backend with `uv`:

```bash
uv sync --extra dev
```

Install frontend dependencies:

```bash
npm install
```

The default dev install uses the deterministic SQLite/vector fallback. To install the full
optional ChromaDB, PyMuPDF, SQLModel, and sentence-transformers stack:

```bash
uv sync --extra dev --extra rag
```

For local runs outside Docker, use repo-local persistent paths:

```bash
mkdir -p data vault inbox artifacts

APP_DATA_DIR="$PWD/data" \
APP_VAULT_DIR="$PWD/vault" \
APP_INBOX_DIR="$PWD/inbox" \
APP_ARTIFACT_DIR="$PWD/artifacts" \
CODEX_OUTPUT_DIR="$PWD/inbox/codex" \
DATABASE_URL="sqlite:///$PWD/data/app.db" \
CHROMA_DIR="$PWD/data/chroma" \
uv run python -m uvicorn ncp_aai.main:app --host 127.0.0.1 --port 8000
```

In another terminal, run the Vite dev server:

```bash
npm run dev
```

The frontend dev server proxies `/api`, `/admin`, and `/health` to FastAPI.

Useful host commands for local development outside Docker:

```bash
uv run ncp-aai init-db
uv run ncp-aai import-objectives
uv run ncp-aai ingest ./nvt-study-guide-new-agentic-ai-cert-exam-4230000.pdf --objective-id objective-1.1 --topic-id topic-1.1
uv run ncp-aai query "agent architecture and human agent interaction"
uv run ncp-aai investigate "Design user interfaces for intuitive human-agent interaction"
```

`investigate` resolves a topic ID or objective title, imports objectives if needed, auto-ingests
the bundled study guide when the topic has no indexed sources, retrieves local context, and writes a
grounded note plus quiz to the configured vault. The current provider is the deterministic local
stub, so it is useful for creating study material now but should still be replaced or reviewed with a
real agent/Codex synthesis pass for final-quality notes.

If the app is running with Docker Compose, run CLI commands inside the container so they use the same
mounted `data`, `vault`, `inbox`, and `artifacts` directories as the web app:

```bash
docker compose exec app ncp-aai investigate "Design user interfaces for intuitive human-agent interaction"
```

Build the production web bundle served by FastAPI:

```bash
npm run build
```

Run validation:

```bash
uv run ruff check src tests
uv run pytest -q
npm run test:web
```

## Docker Without Compose

Build the image:

```bash
docker build -t ncp-aai .
```

Then run:

```bash
mkdir -p data vault inbox artifacts

docker run --rm -p 48673:8000 \
  --env-file .env \
  -v "$PWD/data:/app/data" \
  -v "$PWD/vault:/app/vault" \
  -v "$PWD/inbox:/app/inbox" \
  -v "$PWD/artifacts:/app/artifacts" \
  ncp-aai
```

The app should then be available at:

```text
http://localhost:48673/
http://localhost:48673/health
```

The helper script `scripts/dev_docker_run.sh` runs the same mount layout.

## First Implementation Path

The MVP should follow the implementation plan in order:

1. Create the Python backend skeleton. Done.
2. Add the single-container Docker runtime. Done.
3. Add SQLite persistence and objective import from `EXAM_OBJECTIVES.md`. Done.
4. Implement local file ingestion and retrieval. Done for local files with deterministic fallback.
5. Add the Codex provider adapter and investigation job model. Done for operator-driven ingestion.
6. Generate notes, citations, quizzes, and exercises. Partially done: ingestion, validation, quiz
   attempts, feedback, and exercise records exist.
7. Build the React/Vite study web app. MVP done.
8. Add broader integration, Docker smoke, persistence restore documentation, and setup docs. In progress.

See [`plan/feature-agentic-study-platform-1.md`](./plan/feature-agentic-study-platform-1.md) for the task-level breakdown.

## Repository Contents

| Path | Purpose |
|---|---|
| `PRD.md` | Product requirements for the agentic study platform |
| `plan/feature-agentic-study-platform-1.md` | MVP implementation plan |
| `EXAM_OBJECTIVES.md` | Structured NCP-AAI objective tracker |
| `SPECS.md` | Original study engine concept |
| `nvt-study-guide-new-agentic-ai-cert-exam-4230000.pdf` | Local certification study guide source |
| `skills-lock.json` | Skill/tooling lock metadata |
| `pyproject.toml` | Python package metadata and tooling |
| `package.json` | React/Vite frontend metadata and scripts |
| `PRODUCT.md` | Product register, users, purpose, anti-references, and design principles |
| `DESIGN.md` | Visual system, tokens, layout, component, and state guidance |
| `src/ncp_aai/` | FastAPI backend, ingestion, RAG, jobs, and synthesis modules |
| `src/web/` | React/Vite study web app |
| `tests/` | Backend test suite |
| `Dockerfile` | Single-container backend runtime |

## Development Notes

- Keep generated data out of git.
- Do not commit `.env`, API keys, local databases, Chroma indexes, downloaded source corpora, or generated study output.
- Prefer deterministic schemas and explicit provenance for all source and generated records.
- The first app version should work with local ingestion and local RAG even before external web or YouTube collection is added.
- The SQLite database should live under `/app/data` in the container, backed by the host `./data` directory.

## License

No license has been selected yet.
