# ncp-aai

## Repo state

Spec-only repository — no code, no build system, no tests yet.

## Source of truth

- **SPECS.md** — authoritative design document for the NCP-AAI study engine.
- The vision: a self-improving study environment using Obsidian + ChromaDB (RAG), Hermes Agent (investigation/learning), OpenCode (scaffolding/glue), and Lavish Editor (interactive study loop).

## Tech stack (declared in SPECS.md, not yet instantiated)

| Component | Role |
|-----------|------|
| Python | RAG pipeline (`rag_engine.py`) |
| ChromaDB | Local vector store |
| sentence-transformers (`all-MiniLM-L6-v2`) | Embedding model |
| Obsidian | Markdown vault + note management |
| Hermes Agent | Self-improving investigation agent |
| OpenCode | Terminal-based coding agent (scaffolding) |
| Lavish Editor (`kunchenguid/lavish-axi`) | Browser-based interactive HTML artifacts |

## What an agent should know

- **No CI, no lockfiles, no manifests** — all dependencies will need to be installed from scratch.
- **There are zero Python or Node.js projects initialized.** No `pyproject.toml`, `requirements.txt`, or `package.json` exists.
- **The first deliverable** per the spec is `rag_engine.py`: a Python script that watches an Obsidian vault, chunks + embeds markdown via sentence-transformers, stores in ChromaDB, and exposes `query_knowledge_base(topic)`.
- **Lavish** is added as an OpenCode skill: `npx skills add kunchenguid/lavish-axi --skill lavish`.
- **Hermes Agent** needs tools configured: web search, RAG script access, filesystem access to the Obsidian vault.
- The `README.md` is currently just a title — update it when the project has substance.
