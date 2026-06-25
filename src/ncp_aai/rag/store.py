import json
from typing import Any

from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session
from ncp_aai.rag.embeddings import cosine_similarity, get_embedding_provider


class RagStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.embedding_provider = get_embedding_provider(self.settings.embedding_model)

    @property
    def backend_name(self) -> str:
        return "sqlite-vector-fallback"

    def index_chunks(self, chunks: list[dict[str, Any]]) -> int:
        if not chunks:
            return 0
        vectors = self.embedding_provider.embed([chunk["text"] for chunk in chunks])
        with session(self.settings) as conn:
            for chunk, vector in zip(chunks, vectors, strict=True):
                conn.execute(
                    """
                    INSERT INTO vector_entries (id, source_chunk_id, embedding_json, metadata_json)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(source_chunk_id) DO UPDATE SET
                        embedding_json = excluded.embedding_json,
                        metadata_json = excluded.metadata_json
                    """,
                    (
                        f"vec-{chunk['id']}",
                        chunk["id"],
                        json.dumps(vector),
                        json.dumps(chunk.get("metadata", {})),
                    ),
                )
        return len(chunks)

    def query(
        self,
        query_text: str,
        *,
        k: int = 5,
        objective_id: str | None = None,
        topic_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query_vector = self.embedding_provider.embed([query_text])[0]
        with session(self.settings) as conn:
            rows = conn.execute(
                """
                SELECT
                    ve.embedding_json,
                    sc.id AS chunk_id,
                    sc.text,
                    sc.page_start,
                    sc.page_end,
                    sc.section,
                    sc.source_id,
                    sr.title AS source_title,
                    sr.path AS source_path,
                    sr.url AS source_url,
                    o.id AS objective_id,
                    t.id AS topic_id
                FROM vector_entries ve
                JOIN source_chunks sc ON sc.id = ve.source_chunk_id
                JOIN source_records sr ON sr.id = sc.source_id
                LEFT JOIN topic_sources ts ON ts.source_id = sr.id
                LEFT JOIN topics t ON t.id = ts.topic_id
                LEFT JOIN objectives o ON o.id = t.objective_id
                """
            ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            if objective_id and row["objective_id"] != objective_id:
                continue
            if topic_id and row["topic_id"] != topic_id:
                continue
            embedding = json.loads(row["embedding_json"])
            score = cosine_similarity(query_vector, embedding)
            results.append(
                {
                    "chunk_id": row["chunk_id"],
                    "source_id": row["source_id"],
                    "source_title": row["source_title"],
                    "source_path": row["source_path"],
                    "source_url": row["source_url"],
                    "text": row["text"],
                    "page_start": row["page_start"],
                    "page_end": row["page_end"],
                    "section": row["section"],
                    "similarity": score,
                    "objective_id": row["objective_id"],
                    "topic_id": row["topic_id"],
                }
            )

        results.sort(key=lambda item: item["similarity"], reverse=True)
        return results[:k]
