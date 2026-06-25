import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session
from ncp_aai.models import Objective, SourceChunk, SourceRecord, Topic, TopicSource, VectorEntry
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
        with session(self.settings) as db:
            for chunk, vector in zip(chunks, vectors, strict=True):
                vector_insert = sqlite_insert(VectorEntry).values(
                    id=f"vec-{chunk['id']}",
                    source_chunk_id=chunk["id"],
                    embedding_json=json.dumps(vector),
                    metadata_json=json.dumps(chunk.get("metadata", {})),
                )
                db.execute(
                    vector_insert.on_conflict_do_update(
                        index_elements=[VectorEntry.source_chunk_id],
                        set_={
                            "embedding_json": vector_insert.excluded.embedding_json,
                            "metadata_json": vector_insert.excluded.metadata_json,
                        },
                    )
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
        with session(self.settings) as db:
            rows = db.execute(
                select(
                    VectorEntry.embedding_json,
                    SourceChunk.id.label("chunk_id"),
                    SourceChunk.text,
                    SourceChunk.page_start,
                    SourceChunk.page_end,
                    SourceChunk.section,
                    SourceChunk.source_id,
                    SourceRecord.title.label("source_title"),
                    SourceRecord.path.label("source_path"),
                    SourceRecord.url.label("source_url"),
                    Objective.id.label("objective_id"),
                    Topic.id.label("topic_id"),
                )
                .join(SourceChunk, SourceChunk.id == VectorEntry.source_chunk_id)
                .join(SourceRecord, SourceRecord.id == SourceChunk.source_id)
                .outerjoin(TopicSource, TopicSource.source_id == SourceRecord.id)
                .outerjoin(Topic, Topic.id == TopicSource.topic_id)
                .outerjoin(Objective, Objective.id == Topic.objective_id)
            ).all()

        results: list[dict[str, Any]] = []
        for row in rows:
            row_data = row._mapping
            if objective_id and row_data["objective_id"] != objective_id:
                continue
            if topic_id and row_data["topic_id"] != topic_id:
                continue
            embedding = json.loads(row_data["embedding_json"])
            score = cosine_similarity(query_vector, embedding)
            results.append(
                {
                    "chunk_id": row_data["chunk_id"],
                    "source_id": row_data["source_id"],
                    "source_title": row_data["source_title"],
                    "source_path": row_data["source_path"],
                    "source_url": row_data["source_url"],
                    "text": row_data["text"],
                    "page_start": row_data["page_start"],
                    "page_end": row_data["page_end"],
                    "section": row_data["section"],
                    "similarity": score,
                    "objective_id": row_data["objective_id"],
                    "topic_id": row_data["topic_id"],
                }
            )

        results.sort(key=lambda item: item["similarity"], reverse=True)
        return results[:k]
