from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "JIT Adaptive Learning Engine"
    environment: str = "development"
    ollama_model: str = "gemma4:31b-cloud"
    extractor_use_llm: bool = False
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    # Do not make a learner-facing request wait on a surprise model download.
    # Production images should pre-cache this model during their build.
    embedding_local_files_only: bool = True
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection: str = "notes_chunks"
    data_dir: Path = Path(__file__).resolve().parent / ".." / "data"
    qdrant_dir: Path = Path(__file__).resolve().parent / ".." / "data" / "qdrant"
    sqlite_path: Path = Path(__file__).resolve().parent / ".." / "data" / "engine.sqlite3"
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".." / ".env",
        env_prefix="ALE_",
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    if not settings.qdrant_url:
        settings.qdrant_dir.mkdir(parents=True, exist_ok=True)
    return settings
