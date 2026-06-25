from sqlalchemy import select

from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session
from ncp_aai.models import SourceChunk


class CitationValidationError(ValueError):
    pass


def validate_source_chunk_ids(chunk_ids: list[str], settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not chunk_ids:
        msg = "At least one citation is required"
        raise CitationValidationError(msg)

    with session(settings) as db:
        found = set(db.scalars(select(SourceChunk.id).where(SourceChunk.id.in_(chunk_ids))).all())
    missing = sorted(set(chunk_ids) - found)
    if missing:
        msg = f"Unresolved citation source_chunk_id values: {', '.join(missing)}"
        raise CitationValidationError(msg)
