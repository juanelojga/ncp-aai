SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS domains (
        id TEXT PRIMARY KEY,
        number INTEGER NOT NULL UNIQUE,
        name TEXT NOT NULL,
        weight_percent INTEGER NOT NULL,
        summary TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS objectives (
        id TEXT PRIMARY KEY,
        domain_id TEXT NOT NULL REFERENCES domains(id),
        number TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS topics (
        id TEXT PRIMARY KEY,
        objective_id TEXT NOT NULL REFERENCES objectives(id),
        title TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'new',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_records (
        id TEXT PRIMARY KEY,
        source_type TEXT NOT NULL,
        title TEXT NOT NULL,
        path TEXT,
        url TEXT,
        content_type TEXT NOT NULL,
        content_hash TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'ready',
        error TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_chunks (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL REFERENCES source_records(id),
        chunk_index INTEGER NOT NULL,
        text TEXT NOT NULL,
        page_start INTEGER,
        page_end INTEGER,
        section TEXT,
        token_count INTEGER NOT NULL,
        content_hash TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source_id, chunk_index)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS topic_sources (
        topic_id TEXT NOT NULL REFERENCES topics(id),
        source_id TEXT NOT NULL REFERENCES source_records(id),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (topic_id, source_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS investigation_jobs (
        id TEXT PRIMARY KEY,
        topic_id TEXT REFERENCES topics(id),
        status TEXT NOT NULL,
        query TEXT,
        logs_json TEXT NOT NULL DEFAULT '[]',
        gaps_json TEXT NOT NULL DEFAULT '[]',
        artifact_ids_json TEXT NOT NULL DEFAULT '[]',
        error TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        started_at TEXT,
        completed_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_runs (
        id TEXT PRIMARY KEY,
        job_id TEXT REFERENCES investigation_jobs(id),
        provider TEXT NOT NULL,
        model TEXT,
        prompt_version TEXT,
        input_source_ids_json TEXT NOT NULL DEFAULT '[]',
        output_artifact_ids_json TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL,
        error TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notes (
        id TEXT PRIMARY KEY,
        topic_id TEXT REFERENCES topics(id),
        objective_id TEXT REFERENCES objectives(id),
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT,
        prompt_version TEXT,
        vault_path TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS citations (
        id TEXT PRIMARY KEY,
        note_id TEXT REFERENCES notes(id),
        quiz_question_id TEXT REFERENCES quiz_questions(id),
        source_chunk_id TEXT NOT NULL REFERENCES source_chunks(id),
        label TEXT,
        quote TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS quiz_questions (
        id TEXT PRIMARY KEY,
        topic_id TEXT REFERENCES topics(id),
        objective_id TEXT REFERENCES objectives(id),
        prompt TEXT NOT NULL,
        options_json TEXT NOT NULL,
        correct_option INTEGER NOT NULL,
        rationale TEXT NOT NULL,
        difficulty TEXT NOT NULL DEFAULT 'medium',
        concept TEXT,
        provider TEXT NOT NULL,
        model TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS quiz_attempts (
        id TEXT PRIMARY KEY,
        topic_id TEXT REFERENCES topics(id),
        objective_id TEXT REFERENCES objectives(id),
        quiz_question_id TEXT NOT NULL REFERENCES quiz_questions(id),
        selected_option INTEGER NOT NULL,
        is_correct INTEGER NOT NULL,
        score REAL NOT NULL,
        missed_concepts_json TEXT NOT NULL DEFAULT '[]',
        rationale TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS exercise_recommendations (
        id TEXT PRIMARY KEY,
        topic_id TEXT REFERENCES topics(id),
        objective_id TEXT REFERENCES objectives(id),
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'open',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS feedback_items (
        id TEXT PRIMARY KEY,
        topic_id TEXT REFERENCES topics(id),
        body TEXT NOT NULL,
        create_followup_job INTEGER NOT NULL DEFAULT 0,
        followup_job_id TEXT REFERENCES investigation_jobs(id),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vector_entries (
        id TEXT PRIMARY KEY,
        source_chunk_id TEXT NOT NULL UNIQUE REFERENCES source_chunks(id),
        embedding_json TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
]
