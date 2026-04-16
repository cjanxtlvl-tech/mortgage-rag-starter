# Bridge + RAG + Rasa Validation Checklist

Use this checklist to confirm the end-to-end integration is working:

- UI bridge status
- RAG answer path
- Rasa handoff path
- Mixed-intent routing path

## Preconditions

- Full stack is running (RAG API + Rasa + Action server).
- In the UI, enable `/chat` mode (Rasa bridge mode).
- Open: `http://127.0.0.1:8010/ui`

## 1. Bridge Health Check

### UI Check

- The badge should show: **Rasa bridge: connected**

### API Check (optional)

```bash
python3 - <<'PY'
import urllib.request
print(urllib.request.urlopen("http://127.0.0.1:8010/health/rasa", timeout=5).read().decode())
PY
```

### Pass Criteria

- `connected` is `true`

## 2. RAG Baseline Check

### Message

- `What is a DSCR loan?`

### Pass Criteria

- `type` is `rag_response`
- `answer` is non-empty
- `sources` is non-empty

## 3. Application Handoff Check

### Message

- `I want to apply for a mortgage`

### Pass Criteria

- `type` is `start_application`
- `suggested_next_action` is populated (typically `start_rasa_application`)
- Rasa follow-up behavior/message appears

## 4. Loan Officer Handoff Check

### Message

- `Can I talk to a loan officer?`

### Pass Criteria

- `type` is `talk_to_loan_officer`
- `suggested_next_action` is `handoff_to_loan_officer`
- Rasa follow-up behavior/message appears

## 5. Mixed-Intent Check

### Message

- `How much house can I afford and can I get pre-approved?`

### Pass Criteria

- `type` is `rag_then_offer_application`
- Answer includes useful educational context
- Output includes application offer/CTA style next step

## Quick Troubleshooting

### Badge shows disconnected

- Verify Rasa is reachable on `5005`.
- Verify API returns:

```bash
python3 - <<'PY'
import urllib.request
print(urllib.request.urlopen("http://127.0.0.1:8010/health/rasa", timeout=5).read().decode())
PY
```

- If using Docker compose with a different Rasa project:

```bash
RASA_PROJECT_DIR=../my-rasa-bot docker compose -f docker-compose.full-stack.yml up --build
```

### Rasa reachable but no handoff behavior

- Confirm `/chat` mode is enabled in the UI.
- Confirm your Rasa project contains the custom bridge/follow-up actions.

## Result

If all 5 checks pass, your bridge + RAG + Rasa integration is healthy end-to-end.
