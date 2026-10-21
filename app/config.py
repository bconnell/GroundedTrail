"""Validated runtime configuration."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    backend: str = "postgres"
    embeddings: str = "local"
    database_url: str = "postgresql+psycopg://groundedtrail:groundedtrail@localhost:5432/groundedtrail"
    llm_model: str = "gpt-4.1-mini"
    openai_api_key: str | None = None

    @classmethod
    def from_environment(cls) -> "Settings":
        settings = cls(
            backend=os.getenv("GROUNDTRAIL_BACKEND", "postgres"),
            embeddings=os.getenv("GROUNDTRAIL_EMBEDDINGS", "local"),
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            llm_model=os.getenv("GROUNDTRAIL_LLM_MODEL", "gpt-4.1-mini"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )
        if settings.backend not in {"postgres", "memory"}:
            raise ValueError("GROUNDTRAIL_BACKEND must be postgres or memory")
        if settings.embeddings not in {"local", "hash"}:
            raise ValueError("GROUNDTRAIL_EMBEDDINGS must be local or hash")
        if settings.backend == "postgres" and settings.embeddings != "local":
            raise ValueError("Persistent mode requires local model embeddings")
        return settings
