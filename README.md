# NCP-AAI Agentic Study Platform

A local-first study and investigation platform for preparing for the NVIDIA NCP-AAI certification.

The goal is to build a single-user web app that can investigate each exam topic in parts, collect source material from PDFs, official docs, YouTube transcripts, web pages, GitHub, and local notes, then turn that material into grounded study notes, quizzes, exercises, and readiness tracking.

## Current Status

This repository is still in the planning/specification stage.

There is no application code, Docker image, Python package, frontend app, test suite, or build system yet. The current source of truth is the product and implementation documentation:

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

## Planned Docker Usage

The Docker runtime is not implemented yet. The intended shape is:

```bash
mkdir -p data vault inbox artifacts

docker run --rm -p 8000:8000 \
  --env-file .env \
  -v "$PWD/data:/app/data" \
  -v "$PWD/vault:/app/vault" \
  -v "$PWD/inbox:/app/inbox" \
  -v "$PWD/artifacts:/app/artifacts" \
  ncp-aai
```

The app should then be available at:

```text
http://localhost:8000
```

This command is illustrative until the `Dockerfile`, `.env.example`, and app entry point are implemented.

## First Implementation Path

The MVP should follow the implementation plan in order:

1. Create the Python and React/Vite project skeleton.
2. Add the single-container Docker runtime.
3. Add SQLite persistence and objective import from `EXAM_OBJECTIVES.md`.
4. Implement local file ingestion and ChromaDB-backed RAG.
5. Add the Codex provider adapter and investigation job model.
6. Generate notes, citations, quizzes, and exercises.
7. Build the React/Vite study web app.
8. Add tests, Docker smoke checks, persistence restore documentation, and setup docs.

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

## Development Notes

- Keep generated data out of git.
- Do not commit `.env`, API keys, local databases, Chroma indexes, downloaded source corpora, or generated study output.
- Prefer deterministic schemas and explicit provenance for all source and generated records.
- The first app version should work with local ingestion and local RAG even before external web or YouTube collection is added.
- The SQLite database should live under `/app/data` in the container, backed by the host `./data` directory.

## License

No license has been selected yet.
