from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy import text as sql_text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Domain(Base):
    __tablename__ = "domains"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    weight_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )


class Objective(Base):
    __tablename__ = "objectives"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    domain_id: Mapped[str] = mapped_column(ForeignKey("domains.id"), nullable=False)
    number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    objective_id: Mapped[str] = mapped_column(ForeignKey("objectives.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'new'"))
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )


class SourceRecord(Base):
    __tablename__ = "source_records"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'ready'"))
    error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'{}'")
    )
    retrieved_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (UniqueConstraint("source_id", "chunk_index"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_records.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'{}'")
    )
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )


class TopicSource(Base):
    __tablename__ = "topic_sources"

    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_records.id"), primary_key=True)
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )


class InvestigationJob(Base):
    __tablename__ = "investigation_jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    query: Mapped[str | None] = mapped_column(Text)
    logs_json: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'[]'"))
    gaps_json: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'[]'"))
    artifact_ids_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'[]'")
    )
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    started_at: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[str | None] = mapped_column(Text)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("investigation_jobs.id"))
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    input_source_ids_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'[]'")
    )
    output_artifact_ids_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'[]'")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'{}'")
    )
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))
    objective_id: Mapped[str | None] = mapped_column(ForeignKey("objectives.id"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    vault_path: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'{}'")
    )
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    note_id: Mapped[str | None] = mapped_column(ForeignKey("notes.id"))
    quiz_question_id: Mapped[str | None] = mapped_column(ForeignKey("quiz_questions.id"))
    source_chunk_id: Mapped[str] = mapped_column(ForeignKey("source_chunks.id"), nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    quote: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))
    objective_id: Mapped[str | None] = mapped_column(ForeignKey("objectives.id"))
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[str] = mapped_column(Text, nullable=False)
    correct_option: Mapped[int] = mapped_column(Integer, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'medium'")
    )
    concept: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'{}'")
    )
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))
    objective_id: Mapped[str | None] = mapped_column(ForeignKey("objectives.id"))
    quiz_question_id: Mapped[str] = mapped_column(ForeignKey("quiz_questions.id"), nullable=False)
    selected_option: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)
    missed_concepts_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'[]'")
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )


class ExerciseRecommendation(Base):
    __tablename__ = "exercise_recommendations"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))
    objective_id: Mapped[str | None] = mapped_column(ForeignKey("objectives.id"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'open'"))
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )


class FeedbackItem(Base):
    __tablename__ = "feedback_items"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    create_followup_job: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sql_text("0")
    )
    followup_job_id: Mapped[str | None] = mapped_column(ForeignKey("investigation_jobs.id"))
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )


class VectorEntry(Base):
    __tablename__ = "vector_entries"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_chunk_id: Mapped[str] = mapped_column(
        ForeignKey("source_chunks.id"), nullable=False, unique=True
    )
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'{}'")
    )
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
