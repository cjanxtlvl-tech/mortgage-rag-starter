from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

TARGET = Path(__file__).resolve().parents[1] / "data" / "raw" / "mortgage_rag_ingestion_answers.json"
GENERIC_NOTE = (
    "General mortgage guidance. Exact eligibility, limits, pricing, and overlays vary by program and lender."
)
REPLACEMENTS = (
    (" percent ", " % "),
    (" % ", " percent "),
    (" preapproval ", " pre-approval "),
    (" pre-approval ", " preapproval "),
    (" condo ", " condominium "),
    (" llc ", " limited liability company "),
    (" dti ", " debt to income "),
    (" pmi ", " private mortgage insurance "),
    (" hoa ", " homeowners association "),
    (" apr ", " annual percentage rate "),
)
ACRONYM_EXPANSIONS = {
    "FHA": "Federal Housing Administration",
    "VA": "Veterans Affairs",
    "USDA": "United States Department of Agriculture",
    "PMI": "Private Mortgage Insurance",
    "DTI": "Debt-to-Income Ratio",
    "APR": "Annual Percentage Rate",
    "HOA": "Homeowners Association",
    "LLC": "Limited Liability Company",
}


def normalize_space(text: str) -> str:
    return " ".join(text.split()).strip()


def normalize_for_search(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9%\-\s]", " ", lowered)
    return normalize_space(lowered)


def variant_phrases(question: str) -> list[str]:
    base = f" {normalize_for_search(question)} "
    variants = {normalize_space(question), normalize_space(base)}
    for old, new in REPLACEMENTS:
        if old in base:
            variants.add(normalize_space(base.replace(old, new)))
    if "mortgage" in base:
        variants.add(normalize_space(base.replace(" mortgage ", " home loan ")))
    if "home loan" in base:
        variants.add(normalize_space(base.replace(" home loan ", " mortgage ")))
    return [v for v in sorted(variants) if v]


def keyword_phrases(tags: Iterable[str]) -> list[str]:
    phrases = []
    for tag in tags:
        value = normalize_space(str(tag).replace("_", " "))
        if value:
            phrases.append(value)
    return sorted(set(phrases))


def acronym_lines(question: str, tags: list[str]) -> list[str]:
    text = f"{question} {' '.join(tags)}"
    lines = []
    for acronym, expansion in ACRONYM_EXPANSIONS.items():
        if acronym.lower() in text.lower():
            lines.append(f"{acronym}: {expansion}")
    return lines


def build_content(entry: dict) -> str:
    question = normalize_space(entry.get("question", ""))
    answer = normalize_space(entry.get("answer", ""))
    tags = [str(tag) for tag in entry.get("tags", [])]
    search_phrases = variant_phrases(question)
    keywords = keyword_phrases(tags)
    acronyms = acronym_lines(question, tags)

    parts = [
        f"Primary question: {question}",
        f"Borrower asks: {question}",
        f"Search phrases: {' | '.join(search_phrases)}",
    ]
    if keywords:
        parts.append(f"Keywords: {'; '.join(keywords)}")
    if acronyms:
        parts.append("Acronyms: " + " | ".join(acronyms))
    parts.append(f"Direct answer: {answer}")
    parts.append(f"Expanded answer: {answer}")
    parts.append(f"Guidance note: {GENERIC_NOTE}")
    return "\n".join(parts)


def main() -> None:
    payload = json.loads(TARGET.read_text(encoding="utf-8"))
    entries = payload.get("entries", [])
    for entry in entries:
        entry["content"] = build_content(entry)

    payload["version"] = "2026-04-18-optimized"
    payload["description"] = (
        "Knowledge chunks answering failed mortgage chatbot questions. "
        "Content format optimized for stronger TF-IDF and FAISS retrieval with question variants, search phrases, and keyword anchors."
    )

    TARGET.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated {TARGET}")
    print(f"Entries optimized: {len(entries)}")


if __name__ == "__main__":
    main()
