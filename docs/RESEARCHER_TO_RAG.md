# Using `ncp-aai-researcher` With The Docker RAG Store

This guide describes how to run the project-scoped `ncp-aai-researcher` Codex
agent, save its results, and ingest the researched evidence into the NCP-AAI app
running in Docker.

## Runtime Shape

The Docker Compose app persists state through host bind mounts:

| Host path | Container path | Purpose |
|---|---|---|
| `./data` | `/app/data` | SQLite database and Chroma data |
| `./inbox` | `/app/inbox` | Files available for source ingestion |
| `./vault` | `/app/vault` | Generated Markdown notes |
| `./artifacts` | `/app/artifacts` | Generated or operator-managed artifacts |

Because these are bind mounts, files written on the host under `./inbox`,
`./data`, `./vault`, or `./artifacts` are visible to the running container.

The current app does not ingest the `ncp-aai-researcher` JSON bundle directly.
Instead, ingest the bundle's source evidence as normal inbox source files, then
use the existing RAG and investigation endpoints.

## Prerequisites

Start the app and import objectives:

```bash
docker compose up --build
curl -X POST http://localhost:48673/admin/import-objectives
```

Confirm the app is healthy:

```bash
curl http://localhost:48673/health
```

## 1. Run The Researcher

Run Codex from the repository root and save the research bundle:

```bash
mkdir -p artifacts/research

codex exec --search -C "$PWD" \
  -o artifacts/research/topic-1.1.bundle.json \
  "Use the custom agent named ncp-aai-researcher to research exactly this objective: objective-1.1 / topic-1.1. Return only the JSON research bundle."
```

If the CLI does not spawn the custom agent from a non-interactive prompt, run an
interactive Codex session in the repo and ask:

```text
Spawn ncp-aai-researcher for objective-1.1 / topic-1.1 and return its JSON bundle.
```

The custom agent is defined at:

```text
.codex/agents/ncp-aai-researcher.toml
```

## 2. Convert The Bundle Into An Inbox Source

The ingestion service accepts supported source files from `./inbox`. Convert the
research bundle's `sources[].content_text` into a Markdown file:

```bash
mkdir -p inbox/research/topic-1.1

jq -r '
  .sources[]
  | "SOURCE_KEY: \(.source_key)\nTITLE: \(.title)\nURL: \(.url)\nQUALITY: \(.quality_label)\nRETRIEVED_AT: \(.retrieved_at)\n\n\(.content_text)\n\n---\n"
' artifacts/research/topic-1.1.bundle.json \
  > inbox/research/topic-1.1/research-sources.md
```

Keep one topic per file when possible. This makes source-to-topic attribution
clearer and keeps retrieval results easier to inspect.

## 3. Ingest Into SQLite And Chroma

Call the app ingestion endpoint with the inbox-relative path:

```bash
curl -X POST http://localhost:48673/api/sources/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "path": "research/topic-1.1/research-sources.md",
    "source_type": "research_bundle",
    "objective_ids": ["objective-1.1"],
    "topic_ids": ["topic-1.1"]
  }'
```

This creates source records and chunks in SQLite, then indexes the chunks in the
configured RAG store under `./data/chroma`.

## 4. Verify Retrieval

Query the RAG endpoint for the topic:

```bash
curl -X POST http://localhost:48673/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "human-agent interaction oversight feedback",
    "topic_id": "topic-1.1",
    "k": 5
  }'
```

The response should include chunks from `research-sources.md`.

## 5. Generate Study Artifacts

After the researched source text is indexed, generate study artifacts from the
topic page or with the API.

For deterministic local output:

```bash
curl -X POST http://localhost:48673/api/topics/topic-1.1/investigations \
  -H "Content-Type: application/json" \
  -d '{"mode":"local_stub","auto_ingest":false}'
```

For host Codex synthesis, start an investigation from the UI or API, then run
the host-side worker against the same bind-mounted paths:

```bash
APP_DATA_DIR="$PWD/data" \
APP_VAULT_DIR="$PWD/vault" \
APP_INBOX_DIR="$PWD/inbox" \
APP_ARTIFACT_DIR="$PWD/artifacts" \
CODEX_OUTPUT_DIR="$PWD/inbox/codex" \
DATABASE_URL="sqlite:///$PWD/data/app.db" \
CHROMA_DIR="$PWD/data/chroma" \
uv run ncp-aai codex-worker --once
```

Generated notes are written under `./vault`, and note, citation, quiz, gap, and
job metadata are persisted in `./data/app.db`.

## Troubleshooting

If ingestion fails with `Inbox source does not exist`, check that the API path is
relative to `./inbox`, not an absolute host path.

If retrieval returns no chunks, verify that the ingest response had non-zero
`chunk_count` and `vector_count`, then query with the matching `topic_id`.

If the Codex worker cannot find requests or responses, verify that
`CODEX_OUTPUT_DIR="$PWD/inbox/codex"` is set when running it on the host.

If you need direct research bundle ingestion later, add a dedicated endpoint that
normalizes `sources[]` into `SourceRecord` and `SourceChunk` rows before calling
`RagStore.index_chunks`.
