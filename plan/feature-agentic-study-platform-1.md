---
goal: Agentic Study Platform MVP Implementation Plan
version: 1.0
date_created: 2026-06-25
last_updated: 2026-06-25
owner: Solo candidate
status: 'Planned'
tags: [feature, architecture, docker, rag, study-app]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan implements the NCP-AAI Agentic Study Platform MVP as a single Dockerized web application with persistent host-mounted data. The MVP replaces Lavish as the primary study interface and introduces a resumable investigation engine, local RAG, source registry, generated notes, quizzes, and readiness tracking.

## 1. Requirements & Constraints

- **REQ-001**: Implement one Docker container that runs the web app, API, local worker, source ingestion, and RAG services.
- **REQ-002**: Persist all user data outside the container through bind-mounted host directories.
- **REQ-003**: Load exam domains and objectives from `EXAM_OBJECTIVES.md`.
- **REQ-004**: Provide a web UI for dashboard, objectives, topic details, investigation jobs, sources, chat, quizzes, and settings.
- **REQ-005**: Implement local ingestion for `.md`, `.txt`, `.html`, and `.pdf` files from `./inbox`.
- **REQ-006**: Implement ChromaDB-backed retrieval over normalized source chunks.
- **REQ-007**: Implement resumable investigation jobs with explicit statuses.
- **REQ-008**: Generate source-backed notes, citations, quiz questions, and exercises for each topic.
- **REQ-009**: Implement an agent provider adapter boundary so Codex, Claude, OpenAI-compatible APIs, Hermes, or local models can be added.
- **REQ-010**: Implement Codex as the initial investigation provider path for MVP.
- **SEC-001**: Store API keys in `.env` or mounted secret files only.
- **SEC-002**: Do not commit generated source content, local databases, API keys, Chroma indexes, or user study data.
- **SEC-003**: Require explicit user confirmation before deleting source records, notes, quiz history, or database state.
- **CON-001**: Use a single container for MVP. Do not require Docker Compose.
- **CON-002**: Do not require Obsidian or Lavish for the primary MVP workflow.
- **CON-003**: Do not depend on network access for local file ingestion and local RAG.
- **CON-004**: Keep module boundaries compatible with future service separation.
- **GUD-001**: Prefer FastAPI and Python for backend, ingestion, RAG, and worker code.
- **GUD-002**: Use SQLite for MVP persistence with the database file stored under `/app/data`.
- **GUD-003**: Prefer deterministic schemas and explicit provenance for every generated artifact.
- **PAT-001**: Store persistent data under `/app/data`, `/app/vault`, `/app/inbox`, and `/app/artifacts` inside the container.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Create the project foundation, Docker runtime, persistent storage layout, and application skeleton.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `pyproject.toml` with FastAPI, Uvicorn, SQLAlchemy or SQLModel, Alembic optional, ChromaDB, sentence-transformers, PyMuPDF, BeautifulSoup, markdown parsing, pydantic-settings, pytest, and ruff dependencies. | | |
| TASK-002 | Create `package.json`, `vite.config.ts`, `src/web/package` structure, and React/Vite dependencies for the study web app. | | |
| TASK-003 | Create `Dockerfile` that installs Python and Node dependencies, builds the React/Vite frontend, exposes port `8000`, creates `/app/data`, `/app/vault`, `/app/inbox`, and `/app/artifacts`, and runs the FastAPI application. | | |
| TASK-004 | Create `.dockerignore` that excludes `.git`, `.env`, `data`, `vault`, `inbox`, `artifacts`, `chroma_db`, caches, and virtual environments. | | |
| TASK-005 | Create `.env.example` with `APP_DATA_DIR=/app/data`, `APP_VAULT_DIR=/app/vault`, `APP_INBOX_DIR=/app/inbox`, `APP_ARTIFACT_DIR=/app/artifacts`, `DATABASE_URL=sqlite:////app/data/app.db`, and provider key placeholders. | | |
| TASK-006 | Create `src/ncp_aai/main.py` with a FastAPI app, health endpoint `GET /health`, API routing, and static serving for the built React/Vite app. | | |
| TASK-007 | Create `src/ncp_aai/config.py` with pydantic settings for persistent paths, database URL, Chroma path, embedding model, and provider configuration. | | |
| TASK-008 | Create `scripts/dev_docker_run.sh` documenting the single-container run command with bind mounts from `./data`, `./vault`, `./inbox`, and `./artifacts`. | | |

### Implementation Phase 2

- GOAL-002: Implement persistent database schema and objective import.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Create `src/ncp_aai/db.py` with SQLite engine creation using `DATABASE_URL` and startup table initialization. | | |
| TASK-010 | Create `src/ncp_aai/models.py` with tables for `Domain`, `Objective`, `Topic`, `InvestigationJob`, `SourceRecord`, `SourceChunk`, `Note`, `Citation`, `QuizQuestion`, `QuizAttempt`, `AgentRun`, and `FeedbackItem`. | | |
| TASK-011 | Create `src/ncp_aai/objectives.py` that parses `EXAM_OBJECTIVES.md` and imports domains, objectives, weights, and objective IDs idempotently. | | |
| TASK-012 | Add API route `POST /admin/import-objectives` to run the objective import. | | |
| TASK-013 | Add API route `GET /api/objectives` returning domains, objectives, topic status, note count, question count, and latest quiz score. | | |

### Implementation Phase 3

- GOAL-003: Implement local ingestion and ChromaDB-backed RAG.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-014 | Create `src/ncp_aai/ingestion/readers.py` with readers for Markdown, text, HTML, and PDF files. | | |
| TASK-015 | Create `src/ncp_aai/ingestion/normalize.py` to convert reader output into normalized text with page or section references. | | |
| TASK-016 | Create `src/ncp_aai/ingestion/chunking.py` with deterministic chunking by heading and token or character window. | | |
| TASK-017 | Create `src/ncp_aai/rag/embeddings.py` using `sentence-transformers/all-MiniLM-L6-v2`. | | |
| TASK-018 | Create `src/ncp_aai/rag/store.py` using ChromaDB persistent client at `/app/data/chroma`. | | |
| TASK-019 | Create API route `POST /api/sources/ingest` that ingests a path from `/app/inbox`, creates `SourceRecord` and `SourceChunk` rows, embeds chunks, and stores vectors. | | |
| TASK-020 | Create API route `POST /api/rag/query` that returns top-k chunks with source IDs, titles, paths, page references, and similarity scores. | | |
| TASK-021 | Add content-hash deduplication so unchanged files do not create duplicate source records or vectors. | | |

### Implementation Phase 4

- GOAL-004: Implement investigation jobs, provider adapter boundary, and the Codex MVP provider path.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-022 | Create `src/ncp_aai/agents/base.py` with `AgentProvider`, `AgentRequest`, `AgentResponse`, `AgentCapability`, and structured error types. | | |
| TASK-023 | Create `src/ncp_aai/agents/codex_provider.py` as the MVP provider adapter for invoking Codex-driven investigation runs and recording structured outputs. | | |
| TASK-024 | Create `src/ncp_aai/agents/local_stub.py` as a deterministic test provider that can synthesize placeholder notes from retrieved chunks for offline tests. | | |
| TASK-025 | Create `src/ncp_aai/jobs/queue.py` with an in-process job queue and persisted job status transitions. | | |
| TASK-026 | Create `src/ncp_aai/jobs/investigation.py` that runs RAG-first investigation, records gaps, and calls the selected provider. | | |
| TASK-027 | Add API route `POST /api/topics/{topic_id}/investigations` to enqueue a bounded investigation pass. | | |
| TASK-028 | Add API route `GET /api/investigations/{job_id}` returning job status, logs, source counts, gaps, and generated artifacts. | | |
| TASK-029 | Store every provider call in `AgentRun` with provider name, model, prompt version, input source IDs, output artifact IDs, token metadata when available, and errors. | | |

### Implementation Phase 5

- GOAL-005: Implement synthesis outputs: notes, citations, quizzes, and exercises.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-030 | Create `src/ncp_aai/synthesis/notes.py` that writes topic notes to `/app/vault` and stores note metadata in the database. | | |
| TASK-031 | Create `src/ncp_aai/synthesis/citations.py` that validates every citation references an existing `SourceRecord` or `SourceChunk`. | | |
| TASK-032 | Create `src/ncp_aai/synthesis/quizzes.py` with a strict quiz question schema: prompt, four options, correct option, rationale, difficulty, objective ID, and citations. | | |
| TASK-033 | Create `src/ncp_aai/synthesis/exercises.py` that generates exercise recommendations from missed quiz concepts and weak objectives. | | |
| TASK-034 | Add API route `GET /api/topics/{topic_id}` returning topic note, sources, citations, quiz questions, exercises, gaps, and job history. | | |
| TASK-035 | Add API route `POST /api/quiz-attempts` that grades answers, stores attempts, and updates readiness metrics. | | |

### Implementation Phase 6

- GOAL-006: Implement the primary study web app.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-036 | Create the React/Vite app shell with routing, API client, shared layout, navigation, loading states, and error states. | | |
| TASK-037 | Create the dashboard view showing domain coverage, readiness scores, active jobs, recent quiz attempts, and weak objectives. | | |
| TASK-038 | Create the objectives view showing all domains and sub-objectives from `EXAM_OBJECTIVES.md`. | | |
| TASK-039 | Create the topic detail view showing note content, citations, source list, quiz questions, exercises, and investigation history. | | |
| TASK-040 | Create the investigation console view with controls to trigger, pause, resume, retry, and inspect jobs. | | |
| TASK-041 | Create the sources view showing source records, extraction status, chunk count, and provenance metadata. | | |
| TASK-042 | Create the quiz interaction view with immediate feedback, rationale, citations, and saved attempt results. | | |
| TASK-043 | Create the settings view showing persistence paths, provider configuration status, embedding model, and app version. | | |

### Implementation Phase 7

- GOAL-007: Add validation, persistence tests, and documentation.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-044 | Add unit tests for objective import, file readers, chunking, deduplication, citation validation, and quiz grading. | | |
| TASK-045 | Add integration test for ingesting a sample Markdown file, embedding chunks, and querying RAG. | | |
| TASK-046 | Add integration test for creating an investigation job and persisting generated note and quiz records. | | |
| TASK-047 | Add frontend tests for dashboard, objectives, topic detail, and quiz interaction views. | | |
| TASK-048 | Add Docker smoke test that starts the container with bind mounts and verifies `GET /health`. | | |
| TASK-049 | Add persistence restore test documentation: create data, remove container, recreate container, verify data remains available. | | |
| TASK-050 | Update `README.md` with project overview, Docker run command, persistence explanation, development setup, and first-use workflow. | | |

## 3. Alternatives

- **ALT-001**: Docker Compose with separate API, frontend, worker, and database services. Rejected for MVP because the user requested a single container.
- **ALT-002**: Keep Lavish as the primary UI. Rejected because the user confirmed the web app should replace Lavish as the main study surface.
- **ALT-003**: Use Postgres in the first single-container version. Deferred because SQLite is simpler for local single-user persistence and can live safely in a bind-mounted directory.
- **ALT-004**: Start with broad web and YouTube collection before local ingestion. Rejected because local ingestion and RAG must work without network access and form the base for all later research.
- **ALT-005**: Hard-code one provider such as Codex or Claude. Rejected because the product requires agent/provider flexibility.
- **ALT-006**: Use FastAPI/Jinja for the MVP frontend. Rejected because the user selected React/Vite for richer study interactions.

## 4. Dependencies

- **DEP-001**: Python 3.11 or newer.
- **DEP-002**: FastAPI.
- **DEP-003**: Uvicorn.
- **DEP-004**: SQLAlchemy or SQLModel.
- **DEP-005**: SQLite.
- **DEP-006**: ChromaDB.
- **DEP-007**: sentence-transformers.
- **DEP-008**: PyMuPDF.
- **DEP-009**: BeautifulSoup or equivalent HTML parser.
- **DEP-010**: Docker.
- **DEP-011**: Node.js and npm for React/Vite build tooling.
- **DEP-012**: React.
- **DEP-013**: Vite.
- **DEP-014**: Codex CLI or callable Codex integration available to the container runtime.
- **DEP-015**: Optional provider SDKs for Claude, OpenAI-compatible APIs, Hermes, and local models.
- **DEP-016**: Optional YouTube transcript library for v1.1.

## 5. Files

- **FILE-001**: `PRD.md` - expanded product requirements.
- **FILE-002**: `plan/feature-agentic-study-platform-1.md` - implementation plan.
- **FILE-003**: `pyproject.toml` - Python project and dependencies.
- **FILE-004**: `Dockerfile` - single-container runtime.
- **FILE-005**: `.dockerignore` - Docker build exclusions.
- **FILE-006**: `.env.example` - environment configuration template.
- **FILE-007**: `package.json` - React/Vite frontend dependencies and scripts.
- **FILE-008**: `vite.config.ts` - Vite build configuration.
- **FILE-009**: `src/ncp_aai/main.py` - FastAPI application entry point.
- **FILE-010**: `src/ncp_aai/config.py` - application settings.
- **FILE-011**: `src/ncp_aai/db.py` - database setup.
- **FILE-012**: `src/ncp_aai/models.py` - persistent schema.
- **FILE-013**: `src/ncp_aai/objectives.py` - objective importer.
- **FILE-014**: `src/ncp_aai/ingestion/readers.py` - file readers.
- **FILE-015**: `src/ncp_aai/ingestion/normalize.py` - text normalization.
- **FILE-016**: `src/ncp_aai/ingestion/chunking.py` - chunking logic.
- **FILE-017**: `src/ncp_aai/rag/embeddings.py` - embedding model wrapper.
- **FILE-018**: `src/ncp_aai/rag/store.py` - ChromaDB integration.
- **FILE-019**: `src/ncp_aai/agents/base.py` - provider adapter contract.
- **FILE-020**: `src/ncp_aai/agents/codex_provider.py` - Codex MVP provider.
- **FILE-021**: `src/ncp_aai/agents/local_stub.py` - deterministic test provider.
- **FILE-022**: `src/ncp_aai/jobs/queue.py` - in-process job queue.
- **FILE-023**: `src/ncp_aai/jobs/investigation.py` - investigation workflow.
- **FILE-024**: `src/ncp_aai/synthesis/notes.py` - note generation and storage.
- **FILE-025**: `src/ncp_aai/synthesis/citations.py` - citation validation.
- **FILE-026**: `src/ncp_aai/synthesis/quizzes.py` - quiz schema and generation.
- **FILE-027**: `src/ncp_aai/synthesis/exercises.py` - exercise recommendations.
- **FILE-028**: `src/web/` - React/Vite study application.
- **FILE-029**: `README.md` - setup and user documentation.

## 6. Testing

- **TEST-001**: Objective import test verifies all domains and objectives from `EXAM_OBJECTIVES.md` are loaded idempotently.
- **TEST-002**: Reader tests verify Markdown, text, HTML, and PDF extraction returns normalized text and provenance.
- **TEST-003**: Deduplication test verifies unchanged files do not create duplicate source records, chunks, or vectors.
- **TEST-004**: Chunking test verifies stable chunk IDs for unchanged content.
- **TEST-005**: RAG integration test verifies a sample document can be ingested and retrieved by semantic query.
- **TEST-006**: Citation validation test rejects notes or quiz questions that reference missing source IDs.
- **TEST-007**: Quiz grading test verifies correct scoring, rationale return, and saved attempt history.
- **TEST-008**: Investigation job test verifies status transitions from `queued` to `complete` or `failed`.
- **TEST-009**: Docker smoke test verifies the app starts and `GET /health` returns success.
- **TEST-010**: Persistence restore test verifies data survives container deletion and recreation when bind-mounted directories remain.

## 7. Risks & Assumptions

- **RISK-001**: Single-container design can become crowded as worker, UI, and source processing grow.
- **RISK-002**: Source collection from web and YouTube can be rate-limited or blocked.
- **RISK-003**: PDF parsing can lose tables, diagrams, or scanned text.
- **RISK-004**: Agent-generated notes can include unsupported claims without strict citation checks.
- **RISK-005**: SQLite can become a bottleneck if background jobs write heavily.
- **RISK-006**: Local embedding model download can fail in offline environments during first setup.
- **ASSUMPTION-001**: The app is single-user and local-first.
- **ASSUMPTION-002**: The user will preserve host-mounted `data`, `vault`, `inbox`, and `artifacts` directories.
- **ASSUMPTION-003**: External LLM provider usage is acceptable when API keys are configured.
- **ASSUMPTION-004**: Lavish is optional after the web app becomes the primary UI.
- **ASSUMPTION-005**: `EXAM_OBJECTIVES.md` remains the objective source of truth until replaced by a structured data file.

## 8. Related Specifications / Further Reading

- [`PRD.md`](../PRD.md)
- [`SPECS.md`](../SPECS.md)
- [`EXAM_OBJECTIVES.md`](../EXAM_OBJECTIVES.md)
- [`AGENTS.md`](../AGENTS.md)
