# Mortgage RAG API — Production Deployment Documentation

This document describes the **current production setup** for the FastAPI-based Retrieval-Augmented Generation (RAG) service used in the mortgage AI stack. It reflects the live Docker/compose configuration and application code in this repository without redesign or changes.

## System Overview

- **Framework:** FastAPI
- **Entry point:** `app.main:app`
- **Server:** `uvicorn`
- **Containerized:** Docker (production Dockerfile + compose)
- **Primary consumer:** Rasa action/server stack

## Core Function

### Endpoint

`POST /ask`

### Request

```json
{
  "question": "string"
}
```

### Response

```json
{
  "type": "rag_then_offer_application",
  "answer": "string",
  "suggested_next_action": "offer_start_rasa_application",
  "display_sources": ["mortgage_knowledge_base.json"],
  "meta": {
    "request_id": "uuid"
  }
}
```

> **Note:** The `type` field can be one of:
`rag_response`, `start_application`, `talk_to_loan_officer`, `rate_request`, `rag_then_offer_application`, `rag_then_offer_loan_officer`, `clarify_goal`, or `fallback`.

## Service Configuration

- **HOST:** `0.0.0.0`
- **PORT:** `8000`

### Health Check

`GET /health` → `{"status": "ok"}`

Additional health endpoint:

`GET /health/rasa` → reports current Rasa connectivity status.

## Docker Setup (Production)

**Dockerfile:** `Dockerfile.production`

Behavior (current production image):

- **Base image:** `python:3.12-slim` (multi-stage)
- **Installs:** `requirements.txt`
- **Copies:**
  - `app/`
  - `data/`
  - `scripts/`
  - `ui/`
- **Runs:**

```bash
python scripts/process_data.py && \
python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 2 \
  --log-level info
```

- **Expose:** `EXPOSE 8000`

## Docker Compose (Production)

**Compose file:** `docker-compose.production.yml`

Service name: `rag-api`

```yaml
services:
  rag-api:
    build:
      context: .
      dockerfile: Dockerfile.production
    container_name: mortgage-rag-api-prod
    restart: always
    environment:
      RASA_WEBHOOK_URL: http://rasa:5005/webhooks/rest/webhook
      HOST: 0.0.0.0
      PORT: 8000
      APP_ENV: production
      PYTHONUNBUFFERED: "1"
    env_file:
      - .env.production
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data:ro
      - rag-logs:/app/logs
    networks:
      - mortgage_network
```

> **Note:** The compose file also defines `rasa` and `rasa-actions` services for the production stack, plus an optional `nginx` reverse proxy.

## Environment Variables (.env.production)

Production uses `.env.production` (generated from `.env.production.template`). Core variables in use:

```plaintext
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
EMBEDDING_MODEL=text-embedding-3-small

APP_ENV=production
HOST=0.0.0.0
PORT=8000

RASA_WEBHOOK_URL=http://rasa:5005/webhooks/rest/webhook
```

Additional defaults from the template include:

```plaintext
DEFAULT_TOP_K=4
DEFAULT_CHUNK_SIZE_WORDS=120
DEFAULT_CHUNK_OVERLAP_WORDS=30
EMBEDDING_DIM_FLOOR=8
```

The settings module also defines:

```plaintext
VECTOR_STORE_PATH=./data/vector_store
```

> **Important:** The current production pipeline persists artifacts under `data/index/` (see **Vector Store** below). `VECTOR_STORE_PATH` exists in settings but is not currently used by the pipeline.

## Data Pipeline

- `scripts/process_data.py` runs **at container start**.
- It loads mortgage JSON data from `data/raw/`.
- It chunks, embeds, and builds the FAISS index.
- It persists artifacts locally before the API starts serving.

## Vector Store

Current production artifacts are stored here:

```
./data/index/
├── mortgage.index.faiss
├── mortgage_chunks.json
└── mortgage_vectorizer.pkl
```

- The directory is created at runtime by `scripts/process_data.py`.
- The `data/` directory is mounted via Docker volume in production.
- **Do not delete** the contents of `data/index/` on production systems unless you intend to rebuild embeddings.

## Rasa Integration

Rasa calls the RAG API using the internal Docker network:

```
http://rag-api:8000/ask
```

Important production constraints:

- Uses the Docker service name (`rag-api`).
- Requires both services on the `mortgage_network` bridge network.
- No external exposure is required for Rasa → RAG traffic.

## Deployment Process

Exact production commands:

```bash
cd /opt/mortgage-stack/rag-api

docker compose down
docker compose up -d --build
```

> If you use the production compose file explicitly:

```bash
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml up -d --build
```

## Testing

### 1) Health Check

```bash
curl http://127.0.0.1:8000/health
```

### 2) Ask Endpoint

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is an FHA loan?"}'
```

## Common Failures

1. **ModuleNotFoundError (pydantic)**
   - Fix: rebuild the container
   - Command: `docker compose up -d --build`

2. **Container restarting**
   - Check logs: `docker logs mortgage-rag-api-prod`

3. **Wrong port (8010 vs 8000)**
   - Ensure Dockerfile + compose both expose/run `8000`

4. **Rasa cannot connect**
   - Network issue or wrong service URL
   - Fix: ensure both services are on the same Docker network (`mortgage_network`).
   - If needed, connect manually:

   ```bash
   docker network connect mortgage_network mortgage-rag-api-prod
   ```

## Logging

- Logs are available via Docker:
  - `docker logs mortgage-rag-api-prod`
  - or `docker compose -f docker-compose.production.yml logs -f rag-api`
- No external logging backend is configured.

## Security Notes

- Never commit `.env.production`.
- Rotate API keys regularly.
- Avoid logging secrets or request payloads containing sensitive data.

## Repo Structure (Production-Relevant)

```
app/
data/
scripts/
ui/
Dockerfile
Dockerfile.production
docker-compose.production.yml
.env.production.template
```

## Final State Expectations

- Service running on **port 8000**
- Rasa can reach `http://rag-api:8000/ask`
- `/health` returns `{"status":"ok"}`
- `/ask` returns structured JSON responses
- Vector store artifacts loaded under `data/index/`
- Container remains stable and healthy