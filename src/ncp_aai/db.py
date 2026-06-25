from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from ncp_aai.config import Settings, get_settings
from ncp_aai.models import Base

SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)


@lru_cache(maxsize=16)
def _engine_for_url(database_url: str) -> Engine:
    engine = create_engine(database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection: Any, _: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.close()

    return engine


def engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    settings.ensure_directories()
    return _engine_for_url(f"sqlite:///{settings.sqlite_path}")


@contextmanager
def session(settings: Settings | None = None) -> Iterator[Session]:
    db = SessionLocal(bind=engine(settings))
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db(settings: Settings | None = None) -> None:
    Base.metadata.create_all(engine(settings))


def model_to_dict(model: Any) -> dict[str, Any]:
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}


def mapping_to_dict(row: Any) -> dict[str, Any]:
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    return dict(row)


def db_exists(path: Path) -> bool:
    return path.exists() and path.is_file()
