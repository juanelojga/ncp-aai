from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session


class CitationValidationError(ValueError):
    pass


def validate_source_chunk_ids(chunk_ids: list[str], settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not chunk_ids:
        msg = "At least one citation is required"
        raise CitationValidationError(msg)

    with session(settings) as conn:
        placeholders = ",".join("?" for _ in chunk_ids)
        rows = conn.execute(
            f"SELECT id FROM source_chunks WHERE id IN ({placeholders})",  # noqa: S608
            tuple(chunk_ids),
        ).fetchall()
    found = {row["id"] for row in rows}
    missing = sorted(set(chunk_ids) - found)
    if missing:
        msg = f"Unresolved citation source_chunk_id values: {', '.join(missing)}"
        raise CitationValidationError(msg)
