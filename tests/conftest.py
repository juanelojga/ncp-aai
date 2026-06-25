from collections.abc import Iterator

import pytest

from ncp_aai.config import get_settings
from ncp_aai.db import init_db


@pytest.fixture
def app_settings(tmp_path, monkeypatch) -> Iterator:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("APP_VAULT_DIR", str(tmp_path / "vault"))
    monkeypatch.setenv("APP_INBOX_DIR", str(tmp_path / "inbox"))
    monkeypatch.setenv("APP_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'data' / 'app.db'}")
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "data" / "chroma"))
    monkeypatch.setenv("CODEX_OUTPUT_DIR", str(tmp_path / "inbox" / "codex"))
    get_settings.cache_clear()
    settings = get_settings()
    settings.ensure_directories()
    init_db(settings)
    yield settings
    get_settings.cache_clear()
