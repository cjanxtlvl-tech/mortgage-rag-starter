import logging
import json
import uuid
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import get_settings
from app.rag.pipeline import RAGPipeline
from app.schemas import AskRequest, AskResponse, ChatRequest, ChatResponse, ResponseMeta
from app.services.router import classify_user_intent
from app.services.source_filter import filter_sources
from app.services import logging_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


def _route_question(payload: AskRequest) -> AskResponse:
    request_id = str(uuid.uuid4())
    decision = classify_user_intent(payload.question)

    if not decision.needs_rag:
        response = AskResponse(
            type=decision.response_type,
            answer=decision.answer,
            suggested_next_action=decision.suggested_next_action,
            display_sources=[],
            meta=ResponseMeta(request_id=request_id),
        )
        logging_service.log_non_rag_route(
            request_id=request_id,
            question=payload.question,
            route_type=decision.response_type,
            reason="Routing decision made before RAG retrieval",
        )
        return response

    try:
        result = pipeline.ask(payload.question, top_k=payload.top_k)
    except Exception as exc:
        logger.error("RAG pipeline error (request_id=%s): %s", request_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    answer = result["answer"]
    raw_sources = result.get("sources", [])
    
    # Filter sources to only display user-facing datasets
    display_sources = filter_sources(raw_sources)

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

    response = AskResponse(
        type=decision.response_type,
        answer=answer,
        suggested_next_action=decision.suggested_next_action,
        display_sources=display_sources,
        meta=ResponseMeta(request_id=request_id),
    )

    # Log detailed retrieval information for debugging and analytics
    logging_service.log_ask_request(
        request_id=request_id,
        question=payload.question,
        response_type=decision.response_type,
        answer=answer,
        suggested_next_action=decision.suggested_next_action,
        retrieval_info={
            "sources_returned": raw_sources,
            "sources_filtered": display_sources,
        },
    )

    return response


def _call_rasa(sender_id: str, message: str) -> list[str]:
    if not settings.rasa_webhook_url:
        return []

    body = json.dumps({"sender": sender_id, "message": message}).encode("utf-8")
    req = urllib_request.Request(
        url=settings.rasa_webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("Rasa bridge call failed: %s", exc)
        return []

    if not isinstance(payload, list):
        return []

    texts: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if text:
            texts.append(text)
    return texts


def _rasa_base_url() -> str:
    if not settings.rasa_webhook_url:
        return ""

    parts = urlsplit(settings.rasa_webhook_url)
    if not parts.scheme or not parts.netloc:
        return settings.rasa_webhook_url.strip()

    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def _is_rasa_available(timeout_seconds: int = 2) -> bool:
    base_url = _rasa_base_url().rstrip("/")
    if not base_url:
        return False

    req = urllib_request.Request(url=f"{base_url}/version", method="GET")
    try:
        with urllib_request.urlopen(req, timeout=timeout_seconds) as response:
            return 200 <= response.status < 500
    except (URLError, HTTPError, TimeoutError):
        return False


@app.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest) -> AskResponse:
    return _route_question(payload)


@app.get("/health/rasa")
def health_rasa() -> dict:
    return {
        "connected": _is_rasa_available(),
        "webhook_url": settings.rasa_webhook_url,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    routed = _route_question(AskRequest(question=payload.question, top_k=payload.top_k))

    rasa_target_types = {
        "start_application",
        "rate_request",
        "talk_to_loan_officer",
    }
    should_route_to_rasa = routed.type in rasa_target_types
    rasa_messages = _call_rasa(payload.sender_id, payload.question) if should_route_to_rasa else []

    return ChatResponse(
        **routed.dict(),
        routed_to_rasa=bool(rasa_messages),
        rasa_messages=rasa_messages,
    )
