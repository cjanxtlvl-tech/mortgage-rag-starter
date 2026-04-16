from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.pipeline import RAGPipeline


def main() -> None:
    settings = get_settings()
    pipeline = RAGPipeline(settings)
    stats = pipeline.build_from_raw()

    print(
        "Built index successfully "
        f"(documents={stats['documents']}, chunks={stats['chunks']})"
    )
    print(f"Index file: {settings.index_path}")
    print(f"Chunks file: {settings.chunks_path}")
    print(f"Vectorizer file: {settings.vectorizer_path}")


if __name__ == "__main__":
    main()
