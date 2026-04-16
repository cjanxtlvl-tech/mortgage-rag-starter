from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Mortgage question from the user")
    top_k: int = Field(default=4, ge=1, le=10)


class AskResponse(BaseModel):
    answer: str
