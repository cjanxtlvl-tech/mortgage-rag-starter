#!/usr/bin/env python3
"""Analyze raw mortgage RAG JSON files for dataset gaps and opportunities.

This script is intentionally read-only for source data files.
It scans JSON under data/raw, extracts Q&A records, and writes a report to:
reports/rag_gap_analysis.json
"""

from __future__ import annotations

import glob
import json
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


QUESTION_FIELDS = ("question", "user_question", "prompt", "query")
ANSWER_FIELDS = ("answer", "response", "content")
CONTAINER_KEYS = ("questions", "qa", "items", "data", "entries")

TOPIC_BUCKETS = {
    "closing_costs": ["closing cost", "cash to close", "fees", "title fee", "escrow"],
    "credit": ["credit score", "fico", "credit repair", "credit history"],
    "down_payment": ["down payment", "3.5%", "5%", "10%", "gift funds"],
    "fha": ["fha", "federal housing administration"],
    "conventional": ["conventional", "fannie mae", "freddie mac"],
    "dti": ["dti", "debt to income", "debt-to-income"],
    "preapproval": ["preapproval", "pre-approval", "prequalification", "pre-qualification"],
    "refinance": ["refinance", "cash-out", "rate and term"],
    "investor": ["dscr", "rental", "investment property", "landlord", "airbnb", "vrbo"],
    "hard_money": ["hard money", "fix and flip", "bridge loan"],
    "seller_concessions": ["seller concession", "seller credit", "closing cost credit"],
    "inspection": ["inspection", "appraisal", "repairs", "property condition"],
    "grants": ["grant", "down payment assistance", "first-time buyer program"],
    "rates": ["interest rate", "mortgage rate", "apr"],
    "monthly_payment": [
        "monthly payment",
        "payment",
        "principal and interest",
        "taxes and insurance",
    ],
}

HIGH_INTENT_PATTERNS = [
    "how much do i need",
    "can i afford",
    "how do i qualify",
    "what do i need to buy",
    "how much is my payment",
    "what are closing costs",
    "can i buy with bad credit",
    "should i refinance",
    "fha vs conventional",
    "dscr loan requirements",
    "how much down payment",
]


def normalize_question(text: str) -> str:
    """Normalize question text for dedupe and matching."""
    normalized = text.lower().strip()
    normalized = re.sub(r"[\s]+", " ", normalized)
    normalized = re.sub(r"[\s\.!?,;:]+$", "", normalized)
    return normalized


def find_first_text(record: Dict[str, Any], fields: Tuple[str, ...]) -> Optional[str]:
    """Return the first non-empty text value from a field list."""
    for field in fields:
        value = record.get(field)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def safe_load_json(file_path: str) -> Tuple[Optional[Any], Optional[str]]:
    """Safely parse JSON and return (payload, error_message)."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def extract_candidate_records(payload: Any, file_path: str) -> Tuple[List[Tuple[Dict[str, Any], str]], List[Dict[str, Any]]]:
    """Extract dict-like candidate records from supported payload formats.

    Returns:
      - candidates: list of (record_dict, source_hint)
      - malformed: records that couldn't be interpreted as usable dict candidates
    """
    candidates: List[Tuple[Dict[str, Any], str]] = []
    malformed: List[Dict[str, Any]] = []

    def collect_from_list(items: Any, source_key: str) -> None:
        if not isinstance(items, list):
            malformed.append(
                {
                    "file": file_path,
                    "reason": f"container_key_not_list:{source_key}",
                    "preview": repr(items)[:200],
                }
            )
            return
        for i, item in enumerate(items):
            if isinstance(item, dict):
                candidates.append((item, f"{source_key}[{i}]"))
            else:
                malformed.append(
                    {
                        "file": file_path,
                        "reason": "list_item_not_object",
                        "source": f"{source_key}[{i}]",
                        "preview": repr(item)[:200],
                    }
                )

    if isinstance(payload, list):
        collect_from_list(payload, "root")
        return candidates, malformed

    if isinstance(payload, dict):
        if any(k in payload for k in QUESTION_FIELDS) or any(k in payload for k in ANSWER_FIELDS):
            candidates.append((payload, "root"))
            return candidates, malformed

        matched_container = False
        for key in CONTAINER_KEYS:
            if key in payload:
                matched_container = True
                collect_from_list(payload.get(key), key)

        if not matched_container:
            malformed.append(
                {
                    "file": file_path,
                    "reason": "dict_without_supported_keys",
                    "keys": sorted(list(payload.keys()))[:50],
                }
            )
        return candidates, malformed

    malformed.append(
        {
            "file": file_path,
            "reason": "unsupported_root_type",
            "root_type": type(payload).__name__,
            "preview": repr(payload)[:200],
        }
    )
    return candidates, malformed


def main() -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    raw_dir = os.path.join(repo_root, "data", "raw")
    report_dir = os.path.join(repo_root, "reports")
    report_path = os.path.join(report_dir, "rag_gap_analysis.json")

    pattern = os.path.join(raw_dir, "**", "*.json")
    json_files = sorted(glob.glob(pattern, recursive=True))

    all_records: List[Dict[str, Any]] = []
    malformed_records: List[Dict[str, Any]] = []

    print("=" * 72)
    print("Mortgage RAG Gap Analyzer")
    print("=" * 72)
    print(f"Scanning: {raw_dir}")
    print(f"Files matched: {len(json_files)}")

    for file_path in json_files:
        payload, error = safe_load_json(file_path)
        if error:
            malformed_records.append(
                {
                    "file": file_path,
                    "reason": "json_load_error",
                    "error": error,
                }
            )
            continue

        candidates, malformed = extract_candidate_records(payload, file_path)
        malformed_records.extend(malformed)

        for candidate, source_hint in candidates:
            question = find_first_text(candidate, QUESTION_FIELDS)
            answer = find_first_text(candidate, ANSWER_FIELDS) or ""

            if not question:
                malformed_records.append(
                    {
                        "file": file_path,
                        "reason": "missing_question_like_field",
                        "source": source_hint,
                        "available_keys": sorted(list(candidate.keys()))[:50],
                    }
                )
                continue

            record = {
                "file": file_path,
                "source": source_hint,
                "question": question,
                "normalized_question": normalize_question(question),
                "answer": answer,
                "recommended_link": candidate.get("recommended_link"),
                "suggested_next_action": candidate.get("suggested_next_action"),
            }
            all_records.append(record)

    # Deduplicate by normalized question and track all occurrences.
    grouped_by_question: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in all_records:
        grouped_by_question[record["normalized_question"]].append(record)

    unique_questions = set(grouped_by_question.keys())

    duplicates = []
    for normalized_q, records in grouped_by_question.items():
        if len(records) > 1:
            duplicates.append(
                {
                    "normalized_question": normalized_q,
                    "count": len(records),
                    "examples": [
                        {"question": r["question"], "file": r["file"], "source": r["source"]}
                        for r in records[:10]
                    ],
                }
            )

    missing_links = [
        {"question": r["question"], "file": r["file"], "source": r["source"]}
        for r in all_records
        if not isinstance(r.get("recommended_link"), str) or not r.get("recommended_link", "").strip()
    ]

    missing_next_actions = [
        {"question": r["question"], "file": r["file"], "source": r["source"]}
        for r in all_records
        if not isinstance(r.get("suggested_next_action"), str)
        or not r.get("suggested_next_action", "").strip()
    ]

    short_answers = [
        {
            "question": r["question"],
            "answer_length": len(r["answer"].strip()),
            "file": r["file"],
            "source": r["source"],
        }
        for r in all_records
        if len(r["answer"].strip()) < 150
    ]

    # Topic coverage counts by UNIQUE normalized questions.
    topic_coverage: Dict[str, int] = {}
    normalized_keywords = {
        topic: [normalize_question(k) for k in keywords]
        for topic, keywords in TOPIC_BUCKETS.items()
    }
    for topic, keywords in normalized_keywords.items():
        count = 0
        for uq in unique_questions:
            if any(keyword in uq for keyword in keywords):
                count += 1
        topic_coverage[topic] = count

    weak_topics = [topic for topic, count in topic_coverage.items() if count < 5]

    missing_high_intent_patterns = []
    for pattern_text in HIGH_INTENT_PATTERNS:
        normalized_pattern = normalize_question(pattern_text)
        if not any(normalized_pattern in uq for uq in unique_questions):
            missing_high_intent_patterns.append(pattern_text)

    suggested_next_topics: List[Dict[str, str]] = []
    for topic in weak_topics:
        suggested_next_topics.append(
            {
                "type": "weak_topic",
                "topic": topic,
                "recommendation": f"Add more Q&A content for '{topic}' (currently below 5 unique questions).",
            }
        )
    for pattern_text in missing_high_intent_patterns:
        suggested_next_topics.append(
            {
                "type": "missing_high_intent_pattern",
                "pattern": pattern_text,
                "recommendation": f"Create user-intent Q&A targeting pattern: '{pattern_text}'.",
            }
        )

    summary = {
        "total_json_files_scanned": len(json_files),
        "total_records_loaded": len(all_records),
        "total_unique_questions": len(unique_questions),
        "duplicate_questions": len(duplicates),
        "entries_missing_recommended_link": len(missing_links),
        "entries_missing_suggested_next_action": len(missing_next_actions),
        "entries_with_short_answers_under_150_chars": len(short_answers),
        "malformed_records": len(malformed_records),
    }

    report = {
        "summary": summary,
        "topic_coverage": topic_coverage,
        "weak_topics": weak_topics,
        "duplicates": duplicates,
        "missing_links": missing_links,
        "missing_next_actions": missing_next_actions,
        "short_answers": short_answers,
        "malformed_records": malformed_records,
        "missing_high_intent_patterns": missing_high_intent_patterns,
        "suggested_next_topics": suggested_next_topics,
    }

    os.makedirs(report_dir, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\nAnalysis complete.")
    print("-" * 72)
    print(f"Total JSON files scanned: {summary['total_json_files_scanned']}")
    print(f"Total records loaded: {summary['total_records_loaded']}")
    print(f"Total unique questions: {summary['total_unique_questions']}")
    print(f"Duplicate questions: {summary['duplicate_questions']}")
    print(f"Missing recommended_link: {summary['entries_missing_recommended_link']}")
    print(f"Missing suggested_next_action: {summary['entries_missing_suggested_next_action']}")
    print(f"Short answers (<150 chars): {summary['entries_with_short_answers_under_150_chars']}")
    print(f"Malformed records: {summary['malformed_records']}")

    print("\nTopic coverage (unique question matches):")
    for topic, count in sorted(topic_coverage.items()):
        marker = " ⚠ weak" if topic in weak_topics else ""
        print(f"  - {topic}: {count}{marker}")

    print("\nMissing high-intent patterns:")
    if missing_high_intent_patterns:
        for item in missing_high_intent_patterns:
            print(f"  - {item}")
    else:
        print("  - None")

    print(f"\nReport written to: {report_path}")


if __name__ == "__main__":
    main()
