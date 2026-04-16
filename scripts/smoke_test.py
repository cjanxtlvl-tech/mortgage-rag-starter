from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_BIN = Path(sys.executable)
HOST = "127.0.0.1"
PORT = 8011
ASK_URL = f"http://{HOST}:{PORT}/ask"
HEALTH_URL = f"http://{HOST}:{PORT}/health"


def post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def wait_for_health(timeout_seconds: int = 20) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.4)
            continue
    raise RuntimeError("Server did not become healthy in time")


def validate_response(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise AssertionError("Expected JSON object response")

    response_type = payload.get("type")
    valid_types = {
        "rag_response",
        "start_application",
        "talk_to_loan_officer",
        "rate_request",
        "rag_then_offer_application",
        "rag_then_offer_loan_officer",
        "clarify_goal",
        "fallback",
    }
    if response_type not in valid_types:
        raise AssertionError("Unexpected response type")

    if "answer" not in payload:
        raise AssertionError("Missing 'answer' field")
    if not isinstance(payload["answer"], str) or not payload["answer"].strip():
        raise AssertionError("'answer' must be a non-empty string")

    if "suggested_next_action" not in payload:
        raise AssertionError("Missing 'suggested_next_action' field")

    if "display_sources" not in payload or not isinstance(payload["display_sources"], list):
        raise AssertionError("Missing or invalid 'display_sources' field")

    if "meta" not in payload or not isinstance(payload["meta"], dict):
        raise AssertionError("Missing or invalid 'meta' field")
    
    if "request_id" not in payload["meta"] or not payload["meta"]["request_id"]:
        raise AssertionError("Missing or invalid 'request_id' in meta")

    rag_based_types = {"rag_response", "rag_then_offer_application", "rag_then_offer_loan_officer"}
    if response_type in rag_based_types and len(payload["display_sources"]) == 0:
        raise AssertionError("RAG-based responses must include at least one display_source")

    if response_type not in rag_based_types and payload["display_sources"]:
        raise AssertionError("Non-RAG responses must not include display_sources")


def run() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for the /ask smoke test")

    print("[1/3] Building index artifacts")
    build_cmd = [str(PYTHON_BIN), str(PROJECT_ROOT / "scripts" / "process_data.py")]
    subprocess.run(build_cmd, check=True, cwd=str(PROJECT_ROOT))

    print("[2/3] Starting API server")
    server_cmd = [
        str(PYTHON_BIN),
        "-m",
        "uvicorn",
        "--app-dir",
        str(PROJECT_ROOT),
        "app.main:app",
        "--host",
        HOST,
        "--port",
        str(PORT),
    ]
    proc = subprocess.Popen(
        server_cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        wait_for_health()

        print("[3/3] Calling /ask and validating response")
        response = post_json(
            ASK_URL,
            {
                "question": "What is mortgage pre-approval?",
                "top_k": 3,
            },
        )
        validate_response(response)

        apply_response = post_json(
            ASK_URL,
            {
                "question": "I want to apply for a mortgage",
                "top_k": 3,
            },
        )
        validate_response(apply_response)
        if apply_response.get("type") != "start_application":
            raise AssertionError("Expected start_application for apply intent")

        fallback_response = post_json(
            ASK_URL,
            {
                "question": "How do I cook pasta?",
                "top_k": 3,
            },
        )
        validate_response(fallback_response)
        if fallback_response.get("type") != "fallback":
            raise AssertionError("Expected fallback for out-of-scope intent")

        print("Smoke test PASSED")
        print(f"RAG answer length: {len(response.get('answer', ''))}")
        print(f"Apply route type: {apply_response.get('type')}")
        print(f"Fallback route type: {fallback_response.get('type')}")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"Smoke test FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
