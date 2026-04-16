# API Response Format - Quick Reference

## Summary of Changes

### ✅ What Changed

1. **Response Schema**: Updated to separate public data from internal logging
   - Old field: `sources` → New field: `display_sources`
   - Added: `meta.request_id` for request tracking
   - Removed: All internal details from public response

2. **Source Filtering**: Automatic filtering of user-facing vs. internal datasets
   - Public: `mortgage_basics.json`, `mortgage_knowledge_base.json`, `investor_dscr_advanced_dataset.json`, etc.
   - Hidden: `rasa_rag_intent_routing_dataset.json`, `prompts.json`, `config.json`, etc.

3. **Structured Logging**: Detailed internal logs with full retrieval metrics
   - Similarity scores
   - Chunk text and chunk IDs
   - Retrieval context
   - Model details

## New Response Format

### RAG Response
```json
{
  "type": "rag_response",
  "answer": "Pre-approval is a lender's conditional review...",
  "suggested_next_action": null,
  "display_sources": ["mortgage_knowledge_base.json"],
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### Routing Response
```json
{
  "type": "start_application",
  "answer": "Great! We can begin with a few questions...",
  "suggested_next_action": "start_rasa_application",
  "display_sources": [],
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440001"
  }
}
```

## Code Files Updated

| File | Purpose | Changes |
|------|---------|---------|
| `app/schemas.py` | Request/response models | Added `ResponseMeta`, changed `sources` → `display_sources` |
| `app/main.py` | FastAPI endpoint logic | Generate request_id, filter sources, structured logging |
| `app/services/source_filter.py` | Source visibility helper | New: `is_display_source()`, `filter_sources()` |
| `app/services/logging_service.py` | Structured internal logging | New: `log_ask_request()`, `log_non_rag_route()` |
| `scripts/smoke_test.py` | Integration test | Updated to validate new response format |
| `tests/test_response_format.py` | Unit tests | New: 14 tests for filtering and schema |
| `README.md` | Documentation | Updated response examples with new format |

## Internal Logging Features

All detailed information is still captured in server logs:

```python
logging_service.log_ask_request(
    request_id="550e8400-e29b-41d4-a716-446655440000",
    question="What is a DSCR loan?",
    response_type="rag_response",
    answer="A DSCR loan is...",
    retrieval_info={
        "sources_returned": ["investor_dscr_advanced_dataset.json", "rasa_rag_intent_routing_dataset.json"],
        "sources_filtered": ["investor_dscr_advanced_dataset.json"],
    }
)
```

Logs include:
- Full question and answer text
- All retrieved chunks with similarity scores
- Source files (before and after filtering)
- Model name and generation details
- Timestamps and correlation IDs

## Migration Guide

### For API Clients

If you're consuming the `/ask` endpoint:

**Before:**
```python
response = requests.post("http://api/ask", json={"question": "What is pre-approval?"})
sources = response.json()["sources"]  # OLD FIELD
```

**After:**
```python
response = requests.post("http://api/ask", json={"question": "What is pre-approval?"})
sources = response.json()["display_sources"]  # NEW FIELD
request_id = response.json()["meta"]["request_id"]  # Track in logs
```

### For UI Integration

The UI will automatically get:
- Cleaner source attribution (only real knowledge datasets)
- Request IDs for support correlation
- No internal control filenames in attribution

## Quality Assurance

✅ **Test Coverage**:
- 14 unit tests for source filtering and schema
- 8 intent routing tests (existing, still passing)
- Smoke test validates new response format

✅ **Validation**:
- Public response: Clean, no debug info
- Non-RAG responses: Empty display_sources
- RAG responses: Only user-facing sources included
- Request IDs: Always present and unique

## Testing Locally

```bash
# Run all tests
./.venv/bin/python -m unittest discover tests -v

# Run just response format tests
./.venv/bin/python -m unittest tests.test_response_format -v

# Run integration test (requires OPENAI_API_KEY)
./.venv/bin/python scripts/smoke_test.py
```

## Production Deployment

✅ **Ready for production** - No additional configuration needed:
- Source filtering is automatic
- Request IDs are generated per-request
- Logging is structured and machine-readable
- Type-safe with Pydantic validation
- Backward compatible within the same server version (breaking change for API clients)

## Support & Debugging

Use the `request_id` from the response to correlate with server logs:

```bash
# In server logs:
grep "550e8400-e29b-41d4-a716-446655440000" app.log

# Returns full request context:
# - Original question
# - All retrieved chunks with scores
# - Generation details
# - Any errors or fallbacks
```

## Questions?

See full documentation in `docs/api-response-format.md`
