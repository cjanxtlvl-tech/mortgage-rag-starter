# Mortgage Q&A Local RAG Starter

Minimal local RAG starter for mortgage Q&A.

- API: FastAPI
- Endpoint: `POST /ask`
- Retrieval: TF-IDF embeddings + FAISS cosine-style similarity
- Generation: OpenAI LLM with context built from top retrieved chunks
- Routing: lightweight intent router for Rasa handoff and flow-start actions

The endpoint returns a structured routing response for orchestration and Rasa integration.

## Requirements

```bash
pip install -r requirements.txt
```

Recommended (project-local virtual environment):

```bash
cd /home/chester-anderson/projects/mortgage-rag-starter
python3 -m venv .venv
source .venv/bin/activate
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

Set required OpenAI environment variable:

```bash
export OPENAI_API_KEY="your_api_key_here"
```

Optional model override:

```bash
export OPENAI_MODEL="gpt-4o-mini"
```

## Data Input

Place one or more `.json` files in `data/raw/`.

Accepted JSON shapes:
- A list of strings
- A list of objects with fields like `question`, `answer`, `text`, `content`, `title`, or `topic`
- Nested lists/objects (the loader extracts text-like fields)

## Build the Index

```bash
./.venv/bin/python scripts/process_data.py
```

Artifacts are written to `data/index/`:
- `mortgage.index.faiss`
- `mortgage_chunks.json`
- `mortgage_vectorizer.pkl`

## Run the API

```bash
cd /home/chester-anderson/projects/mortgage-rag-starter
./.venv/bin/python -m uvicorn app.main:app --reload
```

If you run the command from another directory, use:

```bash
/home/chester-anderson/projects/mortgage-rag-starter/.venv/bin/python -m uvicorn --app-dir /home/chester-anderson/projects/mortgage-rag-starter app.main:app --reload
```

## Lite Test UI

After starting the API, open this in your browser:

```text
http://127.0.0.1:8000/ui
```

UI features:
- Enter question text
- Choose `top_k` (1-10)
- Submit to `/ask`
- View clean answer

## Ask a Question

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is mortgage pre-approval?"}'
```

Alternative without `curl`:

```bash
./.venv/bin/python - <<'PY'
import json
import urllib.request

url = "http://127.0.0.1:8000/ask"
payload = {"question": "What is mortgage pre-approval?"}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(req, timeout=30) as resp:
    print(resp.read().decode("utf-8"))
PY
```

Example response (RAG question):

```json
{
  "type": "rag_response",
  "answer": "Pre-approval is a lender's conditional review of your income, assets, debts, and credit to estimate how much you may be able to borrow.",
  "suggested_next_action": null,
  "display_sources": ["mortgage_knowledge_base.json"],
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

Example response (routing question):

```json
{
  "type": "start_application",
  "answer": "Great. We can begin with a few questions to help match you with the right mortgage path.",
  "suggested_next_action": "start_rasa_application",
  "display_sources": [],
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440001"
  }
}
```

Expected response format:

```json
{
  "type": "rag_response | start_application | talk_to_loan_officer | rate_request | rag_then_offer_application | rag_then_offer_loan_officer | clarify_goal | fallback",
  "answer": "clean user-facing response",
  "suggested_next_action": "string-or-null",
  "display_sources": ["source_file_names_for_rag_only"],
  "meta": {
    "request_id": "uuid-string"
  }
}
```

Response fields:
- `type`: routing category that downstream orchestrators (like Rasa) should branch on
- `answer`: clean borrower-facing text
- `suggested_next_action`: next orchestration hint for Rasa (`start_rasa_application`, `handoff_to_loan_officer`, etc.)
- `display_sources`: source filenames for RAG-based responses; empty for non-RAG routes. Includes only user-facing knowledge datasets
- `meta.request_id`: unique identifier for request tracking and correlation with server logs

**Note:** Detailed retrieval metrics (similarity scores, full chunk text, etc.) remain in server logs only and are not returned to the public API for cleaner responses.

### Rasa Routing Contract

Use `type` as the primary switch in Rasa or middleware:

- `start_application` -> start mortgage application flow
- `talk_to_loan_officer` -> start loan-officer handoff flow
- `rate_request` -> start rate-quote flow
- `rag_response` -> send answer directly to user
- `rag_then_offer_application` -> send answer and offer application CTA
- `rag_then_offer_loan_officer` -> send answer and offer loan officer CTA
- `clarify_goal` -> ask a guided clarifying question
- `fallback` -> out-of-scope fallback message

### Additional Curl Examples

Start application intent:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"I want to apply for a mortgage"}'
```

Talk to loan officer intent:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Can I talk to a loan officer?"}'
```

Rate request intent:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What rate can I get today?"}'
```

## One-Command Smoke Test

Run a full local smoke test that:
- rebuilds the index
- starts the API temporarily
- sends a POST request to `/ask`
- validates structured routing response shape
- shuts the API down automatically

```bash
./.venv/bin/python scripts/smoke_test.py
```

## Docker Desktop Full Stack (RAG + Rasa + Actions)

You can run the complete integrated stack in Docker Desktop with one compose file:

- `rag-api` (this FastAPI app + UI)
- `rasa` (Rasa server)
- `rasa-actions` (custom action server)

Prerequisites:

- Docker Desktop running
- `OPENAI_API_KEY` in this project's `.env`
- A sibling Rasa project exists. By default compose uses `../mortgage-rasa-chatbot`.

Start everything:

```bash
docker compose -f docker-compose.full-stack.yml up --build
```

If you want to use `my-rasa-bot` instead, run:

```bash
RASA_PROJECT_DIR=../my-rasa-bot docker compose -f docker-compose.full-stack.yml up --build
```

Open:

- UI: `http://127.0.0.1:8010/ui`
- Rasa API: `http://127.0.0.1:5005`
- Rasa Action Server: `http://127.0.0.1:5055`

Notes:

- The first startup may take longer because Rasa trains a model in-container.
- The UI can use `/chat` mode to bridge handoff intents to Rasa.
- To stop and remove containers:

```bash
docker compose -f docker-compose.full-stack.yml down
```

## Troubleshooting

### `ModuleNotFoundError: No module named app`

This usually means the server was started outside the project folder.

Use one of these:

```bash
cd /home/chester-anderson/projects/mortgage-rag-starter
uvicorn app.main:app --reload
```

Or from anywhere:

```bash
/home/chester-anderson/projects/mortgage-rag-starter/.venv/bin/python -m uvicorn --app-dir /home/chester-anderson/projects/mortgage-rag-starter app.main:app --reload
```

### Port Already In Use

If `8000` is busy, run on a different port:

```bash
uvicorn app.main:app --reload --port 8010
```

Update request URLs to match the new port.

### `GET /favicon.ico 404 Not Found` in Logs

If you see this after opening `/ui`, the app is still working.
It means the browser requested a favicon and none is configured yet.

### `OPENAI_API_KEY is not set`

`/ask` now uses the OpenAI API and requires `OPENAI_API_KEY` in the runtime environment.

```bash
export OPENAI_API_KEY="your_api_key_here"
```

## Project Layout

- `app/main.py`: FastAPI app and `/ask` route
- `app/config.py`: local paths and defaults
- `app/schemas.py`: request/response models
- `app/services/router.py`: intent classification and route decisioning
- `app/rag/loader.py`: JSON knowledge loader
- `app/rag/chunking.py`: chunking logic
- `app/rag/embedder.py`: TF-IDF embedding logic
- `app/rag/vector_store.py`: FAISS index build/load/save
- `app/rag/retriever.py`: top-k retrieval
- `app/rag/generator.py`: grounded answer synthesis
- `app/rag/pipeline.py`: orchestration pipeline
- `scripts/process_data.py`: index build entrypoint
- `data/raw/`: source knowledge JSON files
