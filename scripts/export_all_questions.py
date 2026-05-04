#!/usr/bin/env python3
"""Export all normalized questions from raw RAG JSON datasets.

Outputs:
  - data/exports/all_questions.txt
  - data/exports/all_questions_with_source.csv
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


CONTAINER_KEYS = ("data", "items", "entries", "records", "questions", "qa")


def normalize_question(text: str) -> str:
    """Normalize text for stable deduplication."""
    return " ".join(text.split()).strip().lower()


def is_skipped_backup(file_path: Path) -> bool:
    """Return True when file should be excluded as backup-like artifact."""
    name = file_path.name.lower()
    return name.endswith(".bak") or ".bak" in name


def safe_load_json(file_path: Path) -> tuple[Any | None, str | None]:
    """Safely load JSON payload and return (payload, error)."""
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            return json.load(handle), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def iter_candidate_records(payload: Any) -> Iterable[dict[str, Any]]:
    """Yield dict-like records from supported payload formats."""
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item
        return

    if isinstance(payload, dict):
        # direct single-record payload
        if "question" in payload or "input" in payload:
            yield payload

        # container-based payload
        for key in CONTAINER_KEYS:
            items = payload.get(key)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        yield item


def extract_question(record: dict[str, Any]) -> str | None:
    """Extract question-like text from supported fields."""
    for key in ("question", "input"):
        value = record.get(key)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    raw_dir = project_root / "data" / "raw"
    export_dir = project_root / "data" / "exports"
    txt_path = export_dir / "all_questions.txt"
    csv_path = export_dir / "all_questions_with_source.csv"

    export_dir.mkdir(parents=True, exist_ok=True)

    all_raw_files = sorted(path for path in raw_dir.iterdir() if path.is_file())
    skipped_bak_count = 0
    files_processed_count = 0
    malformed_count = 0
    questions_extracted_count = 0

    unique_questions: set[str] = set()
    question_to_sources: dict[str, set[str]] = defaultdict(set)

    for file_path in all_raw_files:
        if is_skipped_backup(file_path):
            skipped_bak_count += 1
            continue

        if file_path.suffix.lower() != ".json":
            continue

        files_processed_count += 1
        payload, error = safe_load_json(file_path)
        if error:
            malformed_count += 1
            print(f"WARNING: Skipping malformed JSON file {file_path.name}: {error}")
            continue

        for record in iter_candidate_records(payload):
            question = extract_question(record)
            if not question:
                continue

            normalized = normalize_question(question)
            if not normalized:
                continue

            questions_extracted_count += 1
            unique_questions.add(normalized)
            question_to_sources[normalized].add(file_path.name)

    sorted_questions = sorted(unique_questions)

    with txt_path.open("w", encoding="utf-8") as handle:
        for question in sorted_questions:
            handle.write(f"{question}\n")

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["question", "source_file"])
        for question in sorted_questions:
            for source_file in sorted(question_to_sources.get(question, set())):
                writer.writerow([question, source_file])

    print("=" * 72)
    print("All Questions Export")
    print("=" * 72)
    print(f"Raw data directory: {raw_dir}")
    print(f"Total files processed: {files_processed_count}")
    print(f"Total files skipped (.bak): {skipped_bak_count}")
    print(f"Total malformed JSON files skipped: {malformed_count}")
    print(f"Total questions extracted: {questions_extracted_count}")
    print(f"Total unique questions: {len(unique_questions)}")
    print(f"TXT export: {txt_path}")
    print(f"CSV export: {csv_path}")

    print("\nTop 20 sample questions:")
    for idx, question in enumerate(sorted_questions[:20], start=1):
        print(f"{idx:>2}. {question}")


if __name__ == "__main__":
    main()
