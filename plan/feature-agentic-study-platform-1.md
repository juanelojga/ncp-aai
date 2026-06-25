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
- **REQ-009**: Implement an agent provider adapter boundary with an output-ingestion path for operator-driven agents (Codex, using its integrated GPT models) plus a seam for later programmatic providers (OpenAI GPT API, Claude, Hermes).
- **REQ-010**: Implement Codex as the MVP provider in **operator-driven** mode: the user runs Codex and the app ingests, validates (citations resolve to stored chunks), indexes, and records provenance on Codex's structured outputs. The app does not invoke Codex headlessly inside the container.
- **REQ-011**: Deliver a study-value vertical slice (PDF ingest → embed → grounded cited answer → ingest one Codex-produced note + quiz for one objective) before building the multi-view web app or the resumable-job state machine.
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

> **Ordering principle (revised):** ship a study-value vertical slice first, then harden and
> broaden. The exam is on 2026-11-04 — the priority is a system that saves study time within
> days, not a feature-complete product. The resumable-job state machine and the multi-view React
> app are deferred until the ingest→embed→grounded-answer→note+quiz loop is proven, because that
> is where the provider and grounding risks live and where they are cheapest to change. Task IDs
> are sequential in execution order.

### Implementation Phase 1 — Study-Value Vertical Slice

- GOAL-001: Prove the core loop end to end for ONE objective — ingest the bundled study-guide
  PDF, embed it, answer a grounded question with a working citation, and synthesize one note + one
  quiz — exposed through a CLI or a single endpoint. Minimal schema subset only; no React, no job
  state machine.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create a minimal `pyproject.toml` (FastAPI, Uvicorn, SQLAlchemy/SQLModel, ChromaDB, sentence-transformers, PyMuPDF, BeautifulSoup, markdown, pydantic-settings, pytest, ruff). No embedded LLM client in the MVP — synthesis is operator-driven via Codex. Defer Node/React tooling to Phase 6 and any programmatic-provider client to a later phase. | | |
| TASK-002 | Create `src/ncp_aai/config.py` (pydantic settings: persistent paths, `DATABASE_URL`, Chroma path, embedding model, Codex output-ingestion directory) and `.env.example` with `APP_DATA_DIR`, `APP_VAULT_DIR`, `APP_INBOX_DIR`, `APP_ARTIFACT_DIR`, and `DATABASE_URL=sqlite:////app/data/app.db`. Leave commented placeholders for future programmatic-provider keys. | | |
| TASK-003 | Create `src/ncp_aai/db.py` (SQLite engine from `DATABASE_URL`, WAL mode, startup init) and a **minimal** `src/ncp_aai/models.py` subset: `Domain`, `Objective`, `SourceRecord`, `SourceChunk`, `Note`, `Citation`, `QuizQuestion`. (Remaining tables added in Phase 2.) | | |
| TASK-004 | Create `src/ncp_aai/objectives.py` parsing `EXAM_OBJECTIVES.md` and importing domains, objectives, weights, and IDs idempotently. | | |
| TASK-005 | Create `src/ncp_aai/ingestion/readers.py` (Markdown, text, HTML, PDF via PyMuPDF), `normalize.py` (page/section-referenced text), and `chunking.py` (deterministic chunking by heading + token/char window). | | |
| TASK-006 | Create `src/ncp_aai/rag/embeddings.py` (`sentence-transformers/all-MiniLM-L6-v2`) and `src/ncp_aai/rag/store.py` (ChromaDB persistent client at `/app/data/chroma`). | | |
| TASK-007 | Create `src/ncp_aai/agents/base.py` (`AgentProvider`, `AgentRequest`, `AgentResponse`, `AgentCapability`, structured errors) and `src/ncp_aai/agents/codex_provider.py` as the MVP **operator-driven** adapter: define the structured Codex output contract (note + citations + quiz JSON/Markdown) and an ingestion entry that parses, validates, and records provenance (`provider=codex`, model, prompt version). | | |
| TASK-008 | Create `src/ncp_aai/agents/local_stub.py` — a deterministic offline provider that emits Codex-shaped placeholder note/quiz output from retrieved chunks, so the ingestion path and tests run without invoking Codex. | | |
| TASK-009 | Create `src/ncp_aai/synthesis/notes.py` (persist ingested Codex note to `/app/vault` + metadata, link each claim to the chunk it cites), `citations.py` (reject any citation that does not resolve to a real `SourceChunk`), and `quizzes.py` (validate the strict quiz schema: prompt, four options, correct option, rationale, difficulty, objective ID, citations). | | |
| TASK-010 | Create a thin entry point that runs the slice end to end: ingest a PDF from `/app/inbox` → chunk/embed → retrieve top-k cited chunks for a query (extractive — no in-app generation in MVP) → ingest one Codex-produced note + quiz for one objective (validated). Expose as a CLI command and/or `POST /api/slice/run`; add `GET /health`. **Milestone gate: this loop works before Phase 2.** | | |

### Implementation Phase 2 — Persistence Foundation & Schema Completion

- GOAL-002: Complete the database schema and the objective/coverage API on top of the proven slice.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | Extend `models.py` with the remaining tables: `Topic`, `InvestigationJob`, `QuizAttempt`, `AgentRun`, `ExerciseRecommendation`, `FeedbackItem`, `TopicSource`. | | |
| TASK-012 | Add API route `POST /admin/import-objectives` to run the objective import. | | |
| TASK-013 | Add API route `GET /api/objectives` returning domains, objectives, topic status, note count, question count, and latest quiz score. | | |
| TASK-014 | Add content-hash deduplication so unchanged files do not create duplicate source records, chunks, or vectors. | | |
| TASK-015 | Add API routes `POST /api/sources/ingest` (ingest a path from `/app/inbox`, create `SourceRecord`/`SourceChunk`, embed, store vectors) and `POST /api/rag/query` (top-k chunks with source IDs, titles, paths, page references, similarity scores). | | |

### Implementation Phase 3 — Investigation Jobs & Provider Adapter Hardening

- GOAL-003: Add the resumable-job machinery and broaden provider support — now that there is real
  synthesis to schedule.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-016 | Create `src/ncp_aai/jobs/queue.py` — an in-process queue running on a **worker thread off the request path**, with persisted job status transitions (`queued`→`collecting_sources`→`extracting`→`synthesizing`→`needs_review`→`complete`/`failed`). | | |
| TASK-017 | Create `src/ncp_aai/jobs/investigation.py` that runs RAG-first investigation, records gaps and unexplored leads, and ingests the operator's Codex output for a bounded pass (the programmatic-provider call seam is reserved for later). | | |
| TASK-018 | Add API routes `POST /api/topics/{topic_id}/investigations` (enqueue a bounded pass) and `GET /api/investigations/{job_id}` (status, logs, source counts, gaps, artifacts). | | |
| TASK-019 | Store every provider call in `AgentRun` with provider name, model, prompt version, input source IDs, output artifact IDs, token metadata when available, and errors. Add a per-run token/cost ceiling guardrail. | | |

### Implementation Phase 4 — Synthesis Outputs Completion

- GOAL-004: Round out synthesis: exercises, full topic API, and graded quiz attempts.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-020 | Create `src/ncp_aai/synthesis/exercises.py` generating exercise recommendations from missed quiz concepts and weak objectives. | | |
| TASK-021 | Add API route `GET /api/topics/{topic_id}` returning note, sources, citations, quiz questions, exercises, gaps, and job history. | | |
| TASK-022 | Add API route `POST /api/quiz-attempts` that grades answers, stores attempts, and updates readiness metrics. **Confirm domain weights sum correctly before computing readiness (see PRD Open Question on the 92% discrepancy).** | | |

### Implementation Phase 5 — Study Web App (React/Vite)

- GOAL-005: Build the multi-view study UI — deferred until the synthesis loop and APIs are proven.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-023 | Create `package.json`, `vite.config.ts`, `src/web/` structure, and React/Vite dependencies; build the app shell with routing, API client, shared layout, navigation, and loading/error states. | | |
| TASK-024 | Update `src/ncp_aai/main.py` to serve the built React/Vite app as static assets alongside the API. | | |
| TASK-025 | Create the dashboard view (domain coverage, readiness scores, active jobs, recent quiz attempts, weak objectives). | | |
| TASK-026 | Create the objectives view (all domains and sub-objectives from `EXAM_OBJECTIVES.md`). | | |
| TASK-027 | Create the topic detail view (note content, citations, source list, quiz questions, exercises, investigation history). | | |
| TASK-028 | Create the investigation console view (trigger, pause, resume, retry, inspect jobs). | | |
| TASK-029 | Create the sources view (source records, extraction status, chunk count, provenance metadata). | | |
| TASK-030 | Create the quiz interaction view (immediate feedback, rationale, citations, saved attempt results). | | |
| TASK-031 | Create the settings view (persistence paths, provider configuration status, embedding model, app version). | | |

### Implementation Phase 6 — Docker Packaging

- GOAL-006: Package the proven app into the single-container deployment.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-032 | Create `Dockerfile` that installs Python and Node dependencies, builds the React/Vite frontend, exposes port `8000`, creates `/app/data`, `/app/vault`, `/app/inbox`, `/app/artifacts`, and runs the FastAPI app. | | |
| TASK-033 | Create `.dockerignore` excluding `.git`, `.env`, `data`, `vault`, `inbox`, `artifacts`, `chroma_db`, caches, and virtual environments. | | |
| TASK-034 | Create `scripts/dev_docker_run.sh` documenting the single-container run command with bind mounts from `./data`, `./vault`, `./inbox`, and `./artifacts`. | | |

### Implementation Phase 7 — Validation, Persistence Tests, Documentation

- GOAL-007: Add validation, persistence tests, and documentation.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-035 | Add unit tests for objective import, file readers, chunking, deduplication, citation validation, and quiz grading. | | |
| TASK-036 | Add integration test for ingesting a sample Markdown file, embedding chunks, and querying RAG. | | |
| TASK-037 | Add integration test for creating an investigation job and persisting generated note and quiz records. | | |
| TASK-038 | Add frontend tests for dashboard, objectives, topic detail, and quiz interaction views. | | |
| TASK-039 | Add Docker smoke test that starts the container with bind mounts and verifies `GET /health`. | | |
| TASK-040 | Add persistence restore test documentation: create data, remove container, recreate container, verify data remains available. | | |
| TASK-041 | Update `README.md` with project overview, Docker run command, persistence explanation, development setup, and first-use workflow. | | |

## 3. Alternatives

- **ALT-001**: Docker Compose with separate API, frontend, worker, and database services. Rejected for MVP because the user requested a single container.
- **ALT-002**: Keep Lavish as the primary UI. Rejected because the user confirmed the web app should replace Lavish as the main study surface.
- **ALT-003**: Use Postgres in the first single-container version. Deferred because SQLite is simpler for local single-user persistence and can live safely in a bind-mounted directory.
- **ALT-004**: Start with broad web and YouTube collection before local ingestion. Rejected because local ingestion and RAG must work without network access and form the base for all later research.
- **ALT-005**: Invoke Codex headlessly/programmatically from inside the container as the MVP engine. Rejected: non-interactive, authenticated Codex invocation in Docker is an unresolved integration cost. Instead Codex runs **operator-driven** (on its integrated GPT models) and the app ingests/validates its outputs — same provider, none of the headless risk. A programmatic OpenAI GPT API provider remains the path for later in-app generation.
- **ALT-006**: Use FastAPI/Jinja for the MVP frontend. Rejected because the user selected React/Vite for richer study interactions — but the React app is now sequenced **after** the vertical slice (Phase 5), not before it.
- **ALT-007**: Build full infrastructure (Docker, full schema, React shell) before any study output. Rejected: it delivers zero study value for weeks against a fixed exam date and hides provider/grounding risk until late. Replaced by the vertical-slice-first ordering (Phase 1).

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
- **DEP-014**: Codex (CLI/IDE) available to the operator, plus a defined structured-output contract the app can ingest (note + citations + quiz JSON/Markdown). No in-container Codex runtime required.
- **DEP-015**: Optional later programmatic provider SDKs for the OpenAI GPT API, Claude, and Hermes for in-app generation.
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
- **FILE-020**: `src/ncp_aai/agents/codex_provider.py` - MVP operator-driven Codex output-ingestion adapter (parse, validate, record provenance).
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
