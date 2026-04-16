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


class ResponseMeta(BaseModel):
    """Metadata for API response."""
    request_id: str = Field(..., description="Unique request identifier for tracking/logging")


class AskResponse(BaseModel):
    """
    Public API response for /ask endpoint.
    
    Contains clean, user-facing information only.
    Detailed retrieval metrics and debug info are kept in internal logs.
    """
    type: ResponseType
    answer: str
    suggested_next_action: str | None = None
    display_sources: list[str] = Field(default_factory=list, description="User-facing knowledge dataset names")
    meta: ResponseMeta


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, description="User message")
    top_k: int = Field(default=4, ge=1, le=10)
    sender_id: str = Field(default="ui-user", min_length=1, description="Rasa sender ID")


class ChatResponse(AskResponse):
    """
    Chat endpoint response, extends AskResponse with Rasa bridge info.
    """
    routed_to_rasa: bool = False
    rasa_messages: list[str] = Field(default_factory=list)
