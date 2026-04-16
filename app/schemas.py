from typing import Literal, Union

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Mortgage question from the user")
    top_k: int = Field(default=4, ge=1, le=10)


class AskRagResponse(BaseModel):
    type: Literal["rag_response"] = "rag_response"
    answer: str


class AskHandoffResponse(BaseModel):
    type: Literal["handoff"] = "handoff"
    action: Literal["start_application", "get_rates", "connect_loan_officer"]


AskResponse = Union[AskRagResponse, AskHandoffResponse]
