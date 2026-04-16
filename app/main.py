import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import get_settings
from app.rag.pipeline import RAGPipeline
from app.schemas import AskRequest, AskResponse
from app.services.router import classify_user_intent

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Mortgage RAG Starter",
    description="Local FastAPI + FAISS starter for grounded mortgage Q&A.",
    version="0.1.0",
)

settings = get_settings()
pipeline = RAGPipeline(settings)
ui_path = settings.project_root / "ui" / "index.html"


@app.on_event("startup")
def warm_index() -> None:
    pipeline.ensure_ready()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    return RedirectResponse(url="/ui")


@app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
def ui() -> HTMLResponse:
    if not ui_path.exists():
        raise HTTPException(status_code=404, detail="UI file not found")
    return HTMLResponse(content=ui_path.read_text(encoding="utf-8"))


@app.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest) -> AskResponse:
    decision = classify_user_intent(payload.question)

    if not decision.needs_rag:
        return AskResponse(
            type=decision.response_type,
            answer=decision.answer,
            suggested_next_action=decision.suggested_next_action,
            sources=[],
        )

    try:
        result = pipeline.ask(payload.question, top_k=payload.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    answer = result["answer"]
    if decision.response_type == "rag_then_offer_application":
        answer = (
            f"{answer}\n\n"
            "If you'd like, we can start a short application flow to match you with the right mortgage path."
        )
    elif decision.response_type == "rag_then_offer_loan_officer":
        answer = (
            f"{answer}\n\n"
            "If you'd prefer, I can also connect you with a loan officer for personalized guidance."
        )

    return AskResponse(
        type=decision.response_type,
        answer=answer,
        suggested_next_action=decision.suggested_next_action,
        sources=result.get("sources", []),
    )
