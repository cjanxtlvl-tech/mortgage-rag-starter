from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

ASK_URL = "http://127.0.0.1:8000/ask"

QUESTIONS = [
    "What happens at closing?",
    "What are closing costs?",
    "What is DTI?",
    "What is an FHA loan?",
    "How do mortgage rates work?",
    "What is refinancing?",
    "What is a DSCR loan?",
]


def post_question(question: str) -> dict:
    req = urllib.request.Request(
        ASK_URL,
        data=json.dumps({"question": question}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def run() -> int:
    failures: list[str] = []
    print("Running mortgage RAG smoke test...\n")

    for idx, question in enumerate(QUESTIONS, start=1):
        try:
            payload = post_question(question)
        except urllib.error.URLError as exc:
            print(f"[{idx}] FAIL - {question}\n    Request error: {exc}\n")
            failures.append(question)
            continue

        response_type = str(payload.get("type") or "")
        answer = str(payload.get("answer") or "").strip()

        is_valid = response_type != "fallback" and bool(answer)
        status = "PASS" if is_valid else "FAIL"
        print(f"[{idx}] {status} - {question}")
        print(f"    type={response_type} answer_len={len(answer)}")

        if not is_valid:
            print(f"    payload={json.dumps(payload, ensure_ascii=False)}")
            failures.append(question)
        print()

    if failures:
        print("SMOKE TEST FAILED")
        print("Failed questions:")
        for q in failures:
            print(f"- {q}")
        return 1

    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())