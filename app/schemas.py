from typing import Literal

from pydantic import BaseModel, Field


ResponseType = Literal[
    "rag_response",
    "start_application",
    "talk_to_loan_officer",
    "rate_request",
    "rag_then_offer_application",
    "rag_then_offer_loan_officer",
    "clarify_goal",
    "fallback",
]


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Mortgage question from the user")
    top_k: int = Field(default=4, ge=1, le=10, description="Optional retrieval depth for RAG flows")


class AskResponse(BaseModel):
    type: ResponseType
    answer: str
    suggested_next_action: str | None = None
    sources: list[str] = Field(default_factory=list)
