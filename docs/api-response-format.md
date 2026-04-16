# API Response Format Cleanup - Implementation Guide

## Overview

This document describes the cleaned-up `/ask` API response format that separates public-facing user data from detailed internal logging.

## Changes Implemented

### 1. Public API Response Format

The `/ask` endpoint now returns a clean, production-ready response:

```json
{
  "type": "rag_response",
  "answer": "A DSCR loan is an investment property mortgage that focuses mainly on the property's cash flow rather than your personal income.",
  "suggested_next_action": null,
  "display_sources": ["investor_dscr_advanced_dataset.json", "mortgage_knowledge_base.json"],
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

#### Field Descriptions

- **type** (`string`): Routing category for downstream orchestrators
  - Valid values: `rag_response`, `start_application`, `talk_to_loan_officer`, `rate_request`, `rag_then_offer_application`, `rag_then_offer_loan_officer`, `clarify_goal`, `fallback`

- **answer** (`string`): Clean, borrower-friendly response text
  - No internal notes, prompts, or debug information included

- **suggested_next_action** (`string | null`): Optional routing hint for orchestrators
  - Used by Rasa or middleware to determine next workflow step
  - Examples: `start_rasa_application`, `handoff_to_loan_officer`

- **display_sources** (`string[]`): User-facing knowledge dataset names
  - Only includes real mortgage knowledge files
  - Empty for non-RAG routes
  - Excludes internal control files, configs, and prompts

- **meta** (`object`): Response metadata
  - **request_id** (`string`): Unique UUID for tracking and correlation with server logs

### 2. Non-RAG Response Example

For routing decisions made before RAG (e.g., application start intent):

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

### 3. Data NOT Returned in Public Response

The following detailed information is kept in internal logs only:

- ❌ Raw retrieved chunks
- ❌ Similarity scores
- ❌ Internal routing decision notes
- ❌ Prompt template text
- ❌ Stack traces
- ❌ Internal control dataset names (e.g., `rasa_rag_intent_routing_dataset.json`)
- ❌ Debug output
- ❌ Model generation details (prompt, tokens, temperature, etc.)

## Implementation Details

### 1. Source Filtering

**File:** `app/services/source_filter.py`

Provides helper functions to determine which source files are appropriate for public display:

```python
def is_display_source(source_file: str) -> bool:
    """
    Determine if a source file should be displayed to end users.
    Returns True only for real knowledge datasets.
    """
    
def filter_sources(sources: list[str]) -> list[str]:
    """Filter a list of sources to only include user-facing datasets."""
```

**Public Datasets** (visible to users):
- `mortgage_basics.json`
- `mortgage_knowledge_base.json`
- `investor_dscr_advanced_dataset.json`
- `mortgage_additional_training.json`
- `mortgage_conversion_dataset.json`

**Internal Control Files** (hidden from users):
- `rasa_rag_intent_routing_dataset.json`
- Any file starting with `_` or `.`
- Any file containing: `prompt`, `config`, `debug`, `internal`, `control`, `routing`

### 2. Structured Logging

**File:** `app/services/logging_service.py`

Captures detailed request/response cycle information for debugging and analytics:

```python
def log_ask_request(
    request_id: str,
    question: str,
    response_type: str,
    answer: str,
    suggested_next_action: str | None = None,
    retrieval_info: dict[str, Any] | None = None,
) -> None:
    """Log structured request with full retrieval details."""

def log_non_rag_route(
    request_id: str,
    question: str,
    route_type: str,
    reason: str = "",
) -> None:
    """Log non-RAG routing decisions."""
```

**Logged Information** (internal only):
- request_id (correlation identifier)
- timestamp
- user question
- response type and answer
- suggested_next_action
- Retrieval details:
  - Number of chunks retrieved
  - Chunk text and source files
  - Similarity scores
  - Model used for generation
- Any errors or fallback reasons

### 3. Response Schema Updates

**File:** `app/schemas.py`

Updated Pydantic models:

```python
class ResponseMeta(BaseModel):
    """Metadata for API response."""
    request_id: str

class AskResponse(BaseModel):
    """Public API response for /ask endpoint."""
    type: ResponseType
    answer: str
    suggested_next_action: str | None = None
    display_sources: list[str]  # Changed from 'sources'
    meta: ResponseMeta
```

The `ChatResponse` extends `AskResponse` with Rasa-specific fields:
```python
class ChatResponse(AskResponse):
    routed_to_rasa: bool = False
    rasa_messages: list[str] = []
```

### 4. Endpoint Implementation

**File:** `app/main.py`

Updated `/ask` endpoint logic:

1. Generate unique `request_id` using UUID
2. Call `classify_user_intent()` to determine routing
3. For non-RAG routes: return immediately with routing answer
4. For RAG routes: call `pipeline.ask()` and filter sources
5. Filter sources using `filter_sources()` helper
6. Log detailed information via `logging_service`
7. Return clean public response with `display_sources` and `meta`

```python
def _route_question(payload: AskRequest) -> AskResponse:
    request_id = str(uuid.uuid4())
    decision = classify_user_intent(payload.question)
    
    # ... routing logic ...
    
    # Filter sources for public display
    display_sources = filter_sources(raw_sources)
    
    # Create response with metadata
    response = AskResponse(
        type=decision.response_type,
        answer=answer,
        suggested_next_action=decision.suggested_next_action,
        display_sources=display_sources,
        meta=ResponseMeta(request_id=request_id),
    )
    
    # Log detailed information
    logging_service.log_ask_request(
        request_id=request_id,
        question=payload.question,
        response_type=decision.response_type,
        answer=answer,
        suggested_next_action=decision.suggested_next_action,
        retrieval_info={ ... }
    )
    
    return response
```

## Request/Response Flow

```
User Question
    ↓
Generate request_id (UUID)
    ↓
Classify Intent (router)
    ↓
Non-RAG Route?
    ├─ YES → Log routing decision → Return response with empty display_sources
    └─ NO
        ↓
        RAG Pipeline (retrieve + generate)
        ↓
        Filter sources (hide internal files)
        ↓
        Log detailed retrieval info (chunks, scores, etc.)
        ↓
        Return clean response with filtered display_sources
```

## Testing

**File:** `tests/test_response_format.py`

Comprehensive test coverage (14 tests):

- Source filtering:
  - Public datasets visibility
  - Internal datasets hidden
  - Hidden file patterns (_, .)
  - Internal keyword patterns
  - Case-insensitive filtering
  - Mixed source filtering

- Response schema:
  - ResponseMeta creation
  - AskResponse structure
  - Default empty display_sources
  - Serialization to JSON

- End-to-end:
  - Mixed source filtering in responses
  - Routing response has empty sources

Run tests:
```bash
./.venv/bin/python -m unittest tests.test_response_format -v
```

## Backward Compatibility

⚠️ **Breaking Change**: The response field `sources` has been renamed to `display_sources`.

Any clients using the `/ask` endpoint will need to update:
- Old: `response.sources`
- New: `response.display_sources`

The ChatResponse (used by `/chat` endpoint) also includes the new fields automatically.

## Configuration

No additional configuration needed. The source filtering is applied automatically based on:
1. A hardcoded list of internal files to exclude
2. Pattern matching for internal naming conventions
3. An explicit list of public datasets

To customize the list of public datasets or internal files, edit `app/services/source_filter.py`:

```python
# User-facing knowledge datasets
PUBLIC_DATASETS = { ... }

# Internal control and routing files
INTERNAL_SOURCES = { ... }
```

## Logging Output

### Example RAG Request Log

```
RAG_REQUEST: {
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-04-15T10:30:45.123456",
  "question": "What is a DSCR loan?",
  "response_type": "rag_response",
  "answer": "A DSCR loan is...",
  "suggested_next_action": null,
  "retrieval": {
    "model_used": "gpt-4o-mini",
    "chunks_retrieved": 3,
    "chunks": [
      {
        "rank": 1,
        "source": "investor_dscr_advanced_dataset.json",
        "chunk_id": 42,
        "score": 0.89,
        "preview": "A DSCR (Debt Service Coverage Ratio) loan is..."
      },
      ...
    ]
  }
}
```

## API Documentation

The `/ask` endpoint in the README has been updated with the new response format, including:
- Public response examples for both RAG and non-RAG routes
- Field descriptions
- Note about internal metrics remaining in server logs

## Production Readiness

✅ **Production-Ready Features:**

1. **Clean responses**: No debug info or internal details exposed
2. **Request tracking**: Every request has a unique ID for debugging
3. **Structured logging**: Detailed logs available via server stdout/logs
4. **Source safety**: Internal files cannot appear in public responses
5. **Modular design**: Easy to extend filtering rules or logging behavior
6. **Type-safe**: Full Pydantic validation ensures response correctness
7. **Unit tested**: 14 tests validate source filtering and schema correctness

## Future Enhancements

Potential improvements:
- Add optional `?include_scores=true` parameter to expose similarity scores on demand
- Implement log aggregation/search for request_id correlation
- Add response time metrics to meta
- Support for response classification/tagging in logs for analytics
- Optional detailed error information for authenticated admin endpoints
