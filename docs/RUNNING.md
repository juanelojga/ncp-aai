# Running NCP-AAI

This runbook covers the standard local Docker Compose path and the main operational flows for the single-container study app.

## Prerequisites

- Docker with the Compose plugin (`docker compose version`)
- Optional: `uv` for local backend development
- Optional: Node.js and npm for local frontend development

## First Run With Docker Compose

Create a local environment file and persistent host directories:

```bash
cp .env.example .env
mkdir -p data vault inbox artifacts
```

Build and start the app:

```bash
docker compose up --build
```

Open the study app:

```text
http://localhost:48673/
```

Check health:

```bash
curl http://localhost:48673/health
```

Compose publishes the container's internal port `8000` on host port `48673` by default. To use a
different host port, run `APP_HOST_PORT=49157 docker compose up --build`.

The first build can be slow because the image installs Python, RAG, and frontend dependencies.

## Persistence

Compose bind-mounts these host directories into the container:

| Host path | Container path | Purpose |
|---|---|---|
| `./data` | `/app/data` | SQLite database, ChromaDB data, settings, job state |
| `./vault` | `/app/vault` | Generated Markdown notes and Obsidian-compatible files |
| `./inbox` | `/app/inbox` | Source files waiting for ingestion |
| `./artifacts` | `/app/artifacts` | Generated exports and study artifacts |

Container rebuilds and `docker compose down` do not delete these folders. To reset local state, stop Compose and delete the host folders:

```bash
docker compose down
rm -rf data vault inbox artifacts
mkdir -p data vault inbox artifacts
```

## Seed Objectives

Import the bundled exam objectives into SQLite:

```bash
curl -X POST http://localhost:48673/admin/import-objectives
```

After importing, refresh `http://localhost:48673/` to see the objective tree.

## Run The Bundled Study Slice

The slice endpoint imports objectives, ingests the bundled study guide PDF, queries the local RAG store, and ingests deterministic Codex-style output for the default objective/topic.

```bash
curl -X POST http://localhost:48673/api/slice/run \
  -H "Content-Type: application/json" \
  -d '{}'
```

To target a different objective or topic:

```bash
curl -X POST http://localhost:48673/api/slice/run \
  -H "Content-Type: application/json" \
  -d '{"objective_id":"objective-1.1","topic_id":"topic-1.1","query":"agent architecture and human agent interaction"}'
```

## Ingest Files From The Inbox

Place supported files in `./inbox` on the host:

```bash
cp ./nvt-study-guide-new-agentic-ai-cert-exam-4230000.pdf ./inbox/study-guide.pdf
```

Ingest by relative inbox path:

```bash
curl -X POST http://localhost:48673/api/sources/ingest \
  -H "Content-Type: application/json" \
  -d '{"path":"study-guide.pdf","source_type":"study_guide_pdf","objective_ids":["objective-1.1"],"topic_ids":["topic-1.1"]}'
```

Query the RAG store:

```bash
curl -X POST http://localhost:48673/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query":"agent architecture and human agent interaction","objective_id":"objective-1.1","k":5}'
```

## Fetch Suggested Readings

`EXAM_OBJECTIVES.md` includes seed reading titles for each exam domain. The suggested-reading
fetcher turns those seeds into indexed RAG sources:

1. Parse domain courses and seed readings from `EXAM_OBJECTIVES.md`.
2. Resolve each seed title to a URL with DuckDuckGo.
3. Fetch the page with `httpx` and extract readable HTML text with BeautifulSoup.
4. Store the page as `source_type="suggested_reading"`.
5. Chunk and index the text, then link it to topics.

Import objectives before fetching so domain and topic IDs exist:

```bash
curl -X POST http://localhost:48673/admin/import-objectives
```

Preview what Domain 1 would fetch without network downloads or database writes:

```bash
curl -X POST http://localhost:48673/api/readings/fetch \
  -H "Content-Type: application/json" \
  -d '{"domain_id":"domain-1","dry_run":true}'
```

Fetch a small batch:

```bash
curl -X POST http://localhost:48673/api/readings/fetch \
  -H "Content-Type: application/json" \
  -d '{"domain_id":"domain-1","limit":2}'
```

Target one topic instead of linking the domain readings to every topic in the domain:

```bash
curl -X POST http://localhost:48673/api/readings/fetch \
  -H "Content-Type: application/json" \
  -d '{"topic_id":"topic-1.2","limit":2}'
```

Available request fields:

| Field | Meaning |
|---|---|
| `domain_id` | Fetch seeds for one imported domain, for example `domain-1`. |
| `topic_id` | Fetch that topic's domain seeds, but link sources only to that topic. |
| `limit` | Maximum number of seed readings to process. Useful for incremental runs. |
| `dry_run` | Return the planned seeds and topic links without resolving URLs or writing sources. |
| `force` | Re-fetch a URL even when an existing source record already has that URL. |

The response contains `counts` and `results`. Result statuses are:

| Status | Meaning |
|---|---|
| `skipped` | Planned only, normally because `dry_run` was true. |
| `fetched` | URL was resolved, page text was fetched, chunks/vectors were created, and topics were linked. |
| `linked` | Existing source URL was reused and linked to the requested topics. |
| `failed` | This reading failed, but the remaining readings continued. Check `error`. |

Verify retrieval from fetched readings:

```bash
curl -X POST http://localhost:48673/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query":"multi-agent orchestration communication protocols","topic_id":"topic-1.3","k":5}'
```

From a Docker Compose runtime, run the CLI inside the container so it uses the same mounted
database and vector store:

```bash
docker compose exec app ncp-aai fetch-readings --domain domain-1 --limit 2 --json
```

For local backend development outside Docker, use the same repo-local environment variables shown
in the Local Development section, then run:

```bash
uv run ncp-aai import-objectives
uv run ncp-aai fetch-readings --domain domain-1 --limit 2 --dry-run --json
uv run ncp-aai fetch-readings --domain domain-1 --limit 2 --json
```

Live fetching requires outbound network access. One failed URL does not stop the rest of the batch.

Run a local investigation. If the app is running through Docker Compose, run the command inside the
container so it uses the same mounted database, vector store, inbox, and vault as the web app:

```bash
docker compose exec app ncp-aai investigate "Design user interfaces for intuitive human-agent interaction"
```

The command accepts either a topic ID such as `topic-1.1` or an imported objective title. It
auto-ingests the bundled study guide for the resolved topic when no indexed chunks exist, then
returns JSON containing the completed job ID, note ID, quiz IDs, vault path, logs, and gaps.

Use the host form only when running the backend directly with the local development environment
variables shown below:

```bash
APP_DATA_DIR="$PWD/data" \
APP_VAULT_DIR="$PWD/vault" \
APP_INBOX_DIR="$PWD/inbox" \
APP_ARTIFACT_DIR="$PWD/artifacts" \
CODEX_OUTPUT_DIR="$PWD/inbox/codex" \
DATABASE_URL="sqlite:///$PWD/data/app.db" \
CHROMA_DIR="$PWD/data/chroma" \
uv run ncp-aai investigate "Design user interfaces for intuitive human-agent interaction"
```

## Inspect And Operate

Check service status:

```bash
docker compose ps
```

Follow app logs:

```bash
docker compose logs -f app
```

Stop the app while keeping persistent data:

```bash
docker compose down
```

Validate the Compose file:

```bash
docker compose config
```

## Local Development

Backend:

```bash
uv sync --extra dev
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

Frontend:

```bash
npm install
npm run dev
```

The Vite dev server proxies `/api`, `/admin`, and `/health` to FastAPI.

## Troubleshooting

Port conflict: Compose defaults to uncommon host port `48673`. If that is already in use, set
`APP_HOST_PORT` to another host port, for example
`APP_HOST_PORT=49157 docker compose up --build`, then open `http://localhost:49157/`.

Stale `.env`: Compose reads `.env` when present. If health shows unexpected paths, compare `.env` with `.env.example` and keep container paths as `/app/...` for Compose.

Missing frontend build: the Docker image builds and copies `src/web/dist` automatically. If running locally outside Docker and `/` returns `Frontend build not found`, run `npm run build` or use `npm run dev`.

Slow first build: the Dockerfile installs frontend packages and Python dependencies. Later builds should reuse Docker layers unless dependency files change.
