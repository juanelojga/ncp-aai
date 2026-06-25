FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    APP_DATA_DIR=/app/data \
    APP_VAULT_DIR=/app/vault \
    APP_INBOX_DIR=/app/inbox \
    APP_ARTIFACT_DIR=/app/artifacts \
    DATABASE_URL=sqlite:////app/data/app.db \
    CHROMA_DIR=/app/data/chroma

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uv /uvx /bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/data /app/vault /app/inbox /app/artifacts

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY EXAM_OBJECTIVES.md PRD.md SPECS.md ./
COPY nvt-study-guide-new-agentic-ai-cert-exam-4230000.pdf ./

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "python", "-m", "uvicorn", "ncp_aai.main:app", "--host", "0.0.0.0", "--port", "8000"]
