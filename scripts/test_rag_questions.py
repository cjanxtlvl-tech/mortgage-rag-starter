"""
Mortgage RAG test runner

What it does:
- Loads questions from a JSON file
- Sends each question to your Rasa REST webhook
- Optionally checks /model/parse
- Marks PASS/FAIL
- Writes CSV + JSON results

Supported input file shapes:
1) {"questions": [{"question": "..."}]}
2) {"entries": [{"question": "..."}]}
3) [{"question": "..."}]
4) ["question 1", "question 2"]

Usage examples:
    python scripts/test_rag_questions.py --input rag_ingestion_questions.json
    python scripts/test_rag_questions.py --input mortgage_rag_ingestion_answers.json --parse
    python scripts/test_rag_questions.py --input mortgage_rag_ingestion_gap_batch.json --webhook http://localhost:5005/webhooks/rest/webhook

Output files:
    - test_results.csv
    - test_results.json
    - test_failures.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

DEFAULT_WEBHOOK = "http://localhost:5005/webhooks/rest/webhook"
DEFAULT_PARSE = "http://localhost:5005/model/parse"
DEFAULT_SENDER = "mortgage_test_runner"

FALLBACK_TEXT_PATTERNS = [
    "[fallback]",
    "i can currently help with mortgage and home-loan questions. if you share your mortgage goal, i can guide your next step.",
]

FALLBACK_INTENTS = {
    "nlu_fallback",
    "out_of_scope",
}


def load_questions(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    items: List[Dict[str, Any]] = []

    if isinstance(payload, dict):
        if isinstance(payload.get("questions"), list):
            raw = payload["questions"]
            for i, item in enumerate(raw, start=1):
                if isinstance(item, dict):
                    q = str(item.get("question", "")).strip()
                    if q:
                        items.append({
                            "id": item.get("id", f"q-{i:03}"),
                            "question": q,
                            "source_batch": item.get("source_batch", ""),
                            "fail_reason": item.get("fail_reason", ""),
                            "detected_intent": item.get("detected_intent", ""),
                        })
                elif isinstance(item, str) and item.strip():
                    items.append({
                        "id": f"q-{i:03}",
                        "question": item.strip(),
                        "source_batch": "",
                        "fail_reason": "",
                        "detected_intent": "",
                    })

        elif isinstance(payload.get("entries"), list):
            raw = payload["entries"]
            for i, item in enumerate(raw, start=1):
                if isinstance(item, dict):
                    q = str(item.get("question", "")).strip()
                    if q:
                        items.append({
                            "id": item.get("id", f"q-{i:03}"),
                            "question": q,
                            "source_batch": item.get("source_batch", ""),
                            "fail_reason": item.get("fail_reason", ""),
                            "detected_intent": item.get("detected_intent", ""),
                        })

    elif isinstance(payload, list):
        for i, item in enumerate(payload, start=1):
            if isinstance(item, dict):
                q = str(item.get("question", "")).strip()
                if q:
                    items.append({
                        "id": item.get("id", f"q-{i:03}"),
                        "question": q,
                        "source_batch": item.get("source_batch", ""),
                        "fail_reason": item.get("fail_reason", ""),
                        "detected_intent": item.get("detected_intent", ""),
                    })
            elif isinstance(item, str) and item.strip():
                items.append({
                    "id": f"q-{i:03}",
                    "question": item.strip(),
                    "source_batch": "",
                    "fail_reason": "",
                    "detected_intent": "",
                })

    if not items:
        raise ValueError(f"No questions found in {path}")

    deduped = []
    seen = set()
    for item in items:
        q = item["question"].strip().lower()
        if q not in seen:
            seen.add(q)
            deduped.append(item)

    return deduped


def extract_text(response_payload: List[Dict[str, Any]]) -> str:
    texts = []
    for item in response_payload:
        if isinstance(item, dict) and item.get("text"):
            texts.append(str(item["text"]))
    return " ".join(texts).strip()


def is_fallback_text(answer_text: str) -> bool:
    if not answer_text.strip():
        return True
    lowered = answer_text.lower().strip()
    return any(pattern in lowered for pattern in FALLBACK_TEXT_PATTERNS)


def send_webhook(question: str, webhook_url: str, sender: str) -> List[Dict[str, Any]]:
    response = requests.post(
        webhook_url,
        json={"sender": sender, "message": question},
        timeout=45,
    )
    response.raise_for_status()
    return response.json()


def send_parse(question: str, parse_url: str) -> Dict[str, Any]:
    response = requests.post(
        parse_url,
        json={"text": question},
        timeout=45,
    )
    response.raise_for_status()
    return response.json()


def parse_intent(parse_payload: Dict[str, Any]) -> Tuple[str, Any]:
    intent = parse_payload.get("intent") or {}
    return intent.get("name", "") or "", intent.get("confidence", None)


def classify(answer_text: str, intent_name: str, parse_checked: bool) -> str:
    if not answer_text.strip():
        return "FAIL_EMPTY"
    if is_fallback_text(answer_text):
        return "FAIL_FALLBACK_TEXT"
    if parse_checked and intent_name.lower().strip() in FALLBACK_INTENTS:
        return "FAIL_FALLBACK_INTENT"
    return "PASS"


def save_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "id",
        "question",
        "status",
        "answer",
        "fallback_text_detected",
        "fallback_intent_detected",
        "parse_intent_name",
        "parse_intent_confidence",
        "source_batch",
        "expected_fail_reason",
        "expected_detected_intent",
        "error",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input JSON file")
    parser.add_argument("--webhook", default=DEFAULT_WEBHOOK, help="Rasa REST webhook URL")
    parser.add_argument("--parse-url", default=DEFAULT_PARSE, help="Rasa parse URL")
    parser.add_argument("--sender", default=DEFAULT_SENDER, help="Sender id")
    parser.add_argument("--parse", action="store_true", help="Check /model/parse too")
    parser.add_argument("--out-prefix", default="test", help="Output prefix, e.g. test => test_results.csv")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    questions = load_questions(input_path)

    results: List[Dict[str, Any]] = []

    print(f"Loaded {len(questions)} questions from {input_path}")

    for idx, item in enumerate(questions, start=1):
        question = item["question"]
        webhook_payload = None
        parse_payload = None
        parse_intent_name = ""
        parse_intent_confidence = None
        parse_checked = False

        try:
            if args.parse:
                try:
                    parse_payload = send_parse(question, args.parse_url)
                    parse_intent_name, parse_intent_confidence = parse_intent(parse_payload)
                    parse_checked = True
                except Exception as exc:
                    parse_payload = {"parse_error": str(exc)}

            webhook_payload = send_webhook(question, args.webhook, args.sender)
            answer = extract_text(webhook_payload)

            status = classify(answer, parse_intent_name, parse_checked)

            row = {
                "id": item["id"],
                "question": question,
                "status": status,
                "answer": answer,
                "fallback_text_detected": status == "FAIL_FALLBACK_TEXT",
                "fallback_intent_detected": status == "FAIL_FALLBACK_INTENT",
                "parse_intent_name": parse_intent_name,
                "parse_intent_confidence": parse_intent_confidence,
                "source_batch": item.get("source_batch", ""),
                "expected_fail_reason": item.get("fail_reason", ""),
                "expected_detected_intent": item.get("detected_intent", ""),
                "error": "",
                "webhook_raw_response": webhook_payload,
                "parse_raw_response": parse_payload,
            }
            results.append(row)

            extra = []
            if parse_checked and parse_intent_name:
                if parse_intent_confidence is not None:
                    extra.append(f"intent={parse_intent_name} ({parse_intent_confidence:.4f})")
                else:
                    extra.append(f"intent={parse_intent_name}")
            suffix = f" | {'; '.join(extra)}" if extra else ""
            print(f"[{idx:03}] {status} - {question}{suffix}")

        except Exception as exc:
            row = {
                "id": item["id"],
                "question": question,
                "status": "ERROR",
                "answer": "",
                "fallback_text_detected": False,
                "fallback_intent_detected": False,
                "parse_intent_name": parse_intent_name,
                "parse_intent_confidence": parse_intent_confidence,
                "source_batch": item.get("source_batch", ""),
                "expected_fail_reason": item.get("fail_reason", ""),
                "expected_detected_intent": item.get("detected_intent", ""),
                "error": str(exc),
                "webhook_raw_response": webhook_payload,
                "parse_raw_response": parse_payload,
            }
            results.append(row)
            print(f"[{idx:03}] ERROR - {question} -> {exc}")

    out_prefix = args.out_prefix
    results_csv = Path(f"{out_prefix}_results.csv")
    results_json = Path(f"{out_prefix}_results.json")
    failures_csv = Path(f"{out_prefix}_failures.csv")

    save_csv(results, results_csv)
    results_json.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    failures = [r for r in results if r["status"] != "PASS"]
    save_csv(failures, failures_csv)

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    fail_text = sum(1 for r in results if r["status"] == "FAIL_FALLBACK_TEXT")
    fail_intent = sum(1 for r in results if r["status"] == "FAIL_FALLBACK_INTENT")
    fail_empty = sum(1 for r in results if r["status"] == "FAIL_EMPTY")
    errors = sum(1 for r in results if r["status"] == "ERROR")

    print("\n===== SUMMARY =====")
    print(f"Total:                {total}")
    print(f"PASS:                 {passed}")
    print(f"FAIL_FALLBACK_TEXT:   {fail_text}")
    print(f"FAIL_FALLBACK_INTENT: {fail_intent}")
    print(f"FAIL_EMPTY:           {fail_empty}")
    print(f"ERROR:                {errors}")
    print(f"\nSaved: {results_csv}")
    print(f"Saved: {results_json}")
    print(f"Saved: {failures_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
