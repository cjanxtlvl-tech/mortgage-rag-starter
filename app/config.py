from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = DATA_DIR / "index"


class Settings(BaseSettings):
    # env-backed settings
    openai_api_key: SecretStr
    openai_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    vector_store_path: str = "./data/vector_store"
    app_env: str = "local"
    rasa_webhook_url: str = "http://127.0.0.1:5005/webhooks/rest/webhook"

    # app defaults
    embedding_dim_floor: int = 8
    default_chunk_size_words: int = 120
    default_chunk_overlap_words: int = 30
    default_top_k: int = 4

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def project_root(self) -> Path:
        return BASE_DIR

    @property
    def raw_data_dir(self) -> Path:
        return DATA_DIR / "raw"

    @property
    def index_dir(self) -> Path:
        return INDEX_DIR

    @property
    def index_path(self) -> Path:
        return INDEX_DIR / "mortgage.index.faiss"

    @property
    def chunks_path(self) -> Path:
        return INDEX_DIR / "mortgage_chunks.json"

    @property
    def vectorizer_path(self) -> Path:
        return INDEX_DIR / "mortgage_vectorizer.pkl"


@lru_cache
def get_settings() -> Settings:
    return Settings()