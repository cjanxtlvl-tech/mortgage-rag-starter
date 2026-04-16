from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    raw_data_dir: Path
    index_dir: Path
    index_path: Path
    chunks_path: Path
    vectorizer_path: Path
    embedding_dim_floor: int = 8
    default_chunk_size_words: int = 120
    default_chunk_overlap_words: int = 30
    default_top_k: int = 4


def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    index_dir = data_dir / "index"
    return Settings(
        project_root=project_root,
        raw_data_dir=data_dir / "raw",
        index_dir=index_dir,
        index_path=index_dir / "mortgage.index.faiss",
        chunks_path=index_dir / "mortgage_chunks.json",
        vectorizer_path=index_dir / "mortgage_vectorizer.pkl",
    )
