from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the local-first backend."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_data_dir: Path = Field(default=Path("/app/data"), alias="APP_DATA_DIR")
    app_vault_dir: Path = Field(default=Path("/app/vault"), alias="APP_VAULT_DIR")
    app_inbox_dir: Path = Field(default=Path("/app/inbox"), alias="APP_INBOX_DIR")
    app_artifact_dir: Path = Field(default=Path("/app/artifacts"), alias="APP_ARTIFACT_DIR")
    database_url: str = Field(default="sqlite:////app/data/app.db", alias="DATABASE_URL")
    chroma_dir: Path = Field(default=Path("/app/data/chroma"), alias="CHROMA_DIR")
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL"
    )
    codex_output_dir: Path = Field(default=Path("/app/inbox/codex"), alias="CODEX_OUTPUT_DIR")
    project_root: Path = Path(__file__).resolve().parents[2]

    @field_validator(
        "app_data_dir",
        "app_vault_dir",
        "app_inbox_dir",
        "app_artifact_dir",
        "chroma_dir",
        "codex_output_dir",
        mode="before",
    )
    @classmethod
    def expand_path(cls, value: str | Path) -> Path:
        return Path(value).expanduser()

    @property
    def sqlite_path(self) -> Path:
        if not self.database_url.startswith("sqlite:///"):
            msg = "Only sqlite:/// database URLs are supported in the MVP backend"
            raise ValueError(msg)
        raw_path = self.database_url.removeprefix("sqlite:///")
        return Path(raw_path)

    @property
    def bundled_study_guide_path(self) -> Path:
        return self.project_root / "nvt-study-guide-new-agentic-ai-cert-exam-4230000.pdf"

    def ensure_directories(self) -> None:
        for directory in (
            self.app_data_dir,
            self.app_vault_dir,
            self.app_inbox_dir,
            self.app_artifact_dir,
            self.chroma_dir,
            self.codex_output_dir,
            self.sqlite_path.parent,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
