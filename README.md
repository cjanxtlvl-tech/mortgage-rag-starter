# Mortgage Q&A Local RAG Starter

Minimal local RAG starter for mortgage Q&A.

- API: FastAPI
- Endpoint: `POST /ask`
- Retrieval: TF-IDF embeddings + FAISS cosine-style similarity
- Generation: OpenAI LLM with context built from top retrieved chunks

The endpoint returns only a clean answer string.

## Requirements

```bash
pip install -r requirements.txt
```

Recommended (project-local virtual environment):

```bash
cd /home/chester-anderson/projects/mortgage-rag-starter
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
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
python scripts/process_data.py
```

Artifacts are written to `data/index/`:
- `mortgage.index.faiss`
- `mortgage_chunks.json`
- `mortgage_vectorizer.pkl`

## Run the API

```bash
cd /home/chester-anderson/projects/mortgage-rag-starter
uvicorn app.main:app --reload
```

If you run the command from another directory, use:

```bash
python -m uvicorn --app-dir /home/chester-anderson/projects/mortgage-rag-starter app.main:app --reload
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
  -d '{"question":"What is mortgage pre-approval?","top_k":4}'
```

Alternative without `curl`:

```bash
python - <<'PY'
import json
import urllib.request

url = "http://127.0.0.1:8000/ask"
payload = {"question": "What is mortgage pre-approval?", "top_k": 4}

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

Example response:

```json
{
  "answer": "Pre-approval is a lender's conditional review of your income, assets, debts, and credit to estimate how much you may be able to borrow. It is stronger than pre-qualification and can help when you submit an offer."
}
```

Expected result: HTTP `200 OK` with a JSON body containing only `answer`.

Response includes:
- `answer`: clean conversational response grounded in retrieved context

## One-Command Smoke Test

Run a full local smoke test that:
- rebuilds the index
- starts the API temporarily
- sends a POST request to `/ask`
- validates `answer`-only response structure
- shuts the API down automatically

```bash
python scripts/smoke_test.py
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
python -m uvicorn --app-dir /home/chester-anderson/projects/mortgage-rag-starter app.main:app --reload
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
- `app/rag/loader.py`: JSON knowledge loader
- `app/rag/chunking.py`: chunking logic
- `app/rag/embedder.py`: TF-IDF embedding logic
- `app/rag/vector_store.py`: FAISS index build/load/save
- `app/rag/retriever.py`: top-k retrieval
- `app/rag/generator.py`: grounded answer synthesis
- `app/rag/pipeline.py`: orchestration pipeline
- `scripts/process_data.py`: index build entrypoint
- `data/raw/`: source knowledge JSON files
