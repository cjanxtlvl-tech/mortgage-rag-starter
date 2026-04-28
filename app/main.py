import logging
import time
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

FALLBACK_OVERRIDE_MIN_SCORE = 0.35
LOW_CONFIDENCE_SCORE = 0.22
FALLBACK_MARKERS = (
    "[fallback]",
    "i can currently help with mortgage and home-loan questions",
)


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


def _is_generic_fallback_text(answer_text: str) -> bool:
    text = (answer_text or "").lower().strip()
    if not text:
        return True
    return any(marker in text for marker in FALLBACK_MARKERS)


def _top_match_score(matches: list[dict]) -> float:
    if not matches:
        return 0.0
    first = matches[0] or {}
    try:
        return float(first.get("score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_question(text: str) -> str:
    return " ".join((text or "").lower().split()).strip()


def _is_mortgage_query(text: str) -> bool:
    mortgage_terms = [
        "mortgage", "loan", "closing", "closing costs", "closing day", "settlement",
        "escrow", "title", "appraisal", "underwriting", "fha", "conventional", "va", "usda",
        "dti", "debt-to-income", "ltv", "credit score", "refinance", "rate", "interest rate",
        "mortgage rate", "preapproval", "pre-approval", "prequalification", "down payment",
        "pmi", "mip", "dscr", "investor loan", "rental income", "hard money", "bridge loan",
        "cash-out", "loan estimate", "clear to close",
    ]
    lowered = (text or "").lower()
    return any(term in lowered for term in mortgage_terms)


def _match_summary(matches: list[dict], limit: int = 3) -> list[dict]:
    summary: list[dict] = []
    for rank, match in enumerate(matches[:limit], start=1):
        metadata = match.get("metadata") or {}
        summary.append(
            {
                "rank": rank,
                "score": round(float(match.get("score") or 0.0), 4),
                "source": str(match.get("source") or "")[:120],
                "title": str(metadata.get("title") or "")[:120],
                "question": str(metadata.get("question") or "")[:160],
            }
        )
    return summary


def _route_question(payload: AskRequest) -> AskResponse:
    request_id = str(uuid.uuid4())
    normalized_question = _normalize_question(payload.question)
    mortgage_topic_detected = _is_mortgage_query(normalized_question)
    decision = classify_user_intent(payload.question)

    logger.info(
        "ask_debug request_id=%s normalized_question=%s mortgage_topic=%s route_type=%s needs_rag=%s",
        request_id,
        normalized_question,
        mortgage_topic_detected,
        decision.response_type,
        decision.needs_rag,
    )

    if not decision.needs_rag:
        # If router picked fallback, attempt a retrieval-based override.
        # This keeps answer quality high for domain questions that the router
        # classified too conservatively.
        if decision.response_type == "fallback":
            try:
                fallback_result = pipeline.ask(payload.question, top_k=payload.top_k)
                fallback_answer = fallback_result.get("answer", "")
                fallback_matches = fallback_result.get("matches", [])
                fallback_score = _top_match_score(fallback_matches)

                logger.info(
                    "ask_debug request_id=%s fallback_override_check top_matches=%s top_score=%.4f",
                    request_id,
                    _match_summary(fallback_matches),
                    fallback_score,
                )

                if fallback_matches and not _is_generic_fallback_text(fallback_answer):
                    raw_sources = fallback_result.get("sources", [])
                    display_sources = fallback_result.get("display_sources", [])
                    recommended_link = fallback_result.get("recommended_link")
                    answer_text = fallback_answer
                    if fallback_score < LOW_CONFIDENCE_SCORE:
                        answer_text = (
                            f"{fallback_answer}\n\n"
                            "This appears to be the closest match from our mortgage guide."
                        )
                    response = AskResponse(
                        type="rag_response",
                        answer=answer_text,
                        recommended_link=recommended_link,
                        suggested_next_action=None,
                        display_sources=display_sources,
                        meta=ResponseMeta(request_id=request_id),
                    )
                    logging_service.log_ask_request(
                        request_id=request_id,
                        question=payload.question,
                        response_type="rag_response",
                        answer=answer_text,
                        suggested_next_action=None,
                        retrieval_info={
                            **logging_service.log_retrieval_debug(
                                request_id=request_id,
                                question=payload.question,
                                matches=fallback_matches,
                                top_k_requested=payload.top_k,
                            ),
                            "model_used": settings.openai_model,
                            "sources_returned": raw_sources,
                            "sources_filtered": display_sources,
                            "recommended_link": recommended_link,
                            "fallback_overridden": True,
                            "fallback_override_score": fallback_score,
                            "fallback_override_threshold": FALLBACK_OVERRIDE_MIN_SCORE,
                        },
                    )
                    logger.info(
                        "ask_debug request_id=%s final_decision=rag_response override=true",
                        request_id,
                    )
                    return response

                # Safety rule: if mortgage topic and any retrieval match, never fallback.
                if fallback_matches and mortgage_topic_detected:
                    best_match = fallback_matches[0]
                    best_text = str(best_match.get("text") or "").strip()
                    metadata = best_match.get("metadata") or {}
                    best_title = str(metadata.get("title") or "").strip()
                    answer_text = best_text or fallback_answer
                    if fallback_score < LOW_CONFIDENCE_SCORE:
                        answer_text = (
                            f"{answer_text}\n\n"
                            "This appears to be the closest match from our mortgage guide."
                        )
                    response = AskResponse(
                        type="rag_response",
                        answer=answer_text,
                        recommended_link=fallback_result.get("recommended_link"),
                        suggested_next_action=None,
                        display_sources=fallback_result.get("display_sources", []) or ([best_title] if best_title else []),
                        meta=ResponseMeta(request_id=request_id),
                    )
                    logger.info(
                        "ask_debug request_id=%s final_decision=rag_response forced_non_fallback top_matches=%s",
                        request_id,
                        _match_summary(fallback_matches),
                    )
                    return response
            except Exception as exc:
                logger.warning(
                    "Fallback override retrieval failed (request_id=%s): %s",
                    request_id,
                    exc,
                )
                # Always return a single, user-friendly fallback message on error
                fallback_text = (
                    "I can currently help with mortgage and home-loan questions. "
                    "If you share your mortgage goal, I can guide your next step."
                )
                response = AskResponse(
                    type="fallback",
                    answer=fallback_text,
                    recommended_link=None,
                    suggested_next_action=None,
                    display_sources=[],
                    meta=ResponseMeta(request_id=request_id),
                )
                logging_service.log_non_rag_route(
                    request_id=request_id,
                    question=payload.question,
                    route_type="fallback",
                    reason="Fallback override failed; returned static fallback message.",
                )
                return response

        response = AskResponse(
            type=decision.response_type,
            answer=decision.answer,
            recommended_link=None,
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
        logger.info("ask_debug request_id=%s final_decision=%s", request_id, decision.response_type)
        return response

    try:
        result = pipeline.ask(
            payload.question,
            top_k=payload.top_k,
        )
    except Exception as exc:
        logger.error("RAG pipeline error (request_id=%s): %s", request_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    answer = result["answer"]
    recommended_link = result.get("recommended_link")
    raw_sources = result.get("sources", [])
    matches = result.get("matches", [])
    display_sources = result.get("display_sources", [])

    if decision.response_type == "rag_then_offer_loan_officer":
        answer = (
            f"{answer}\n\n"
            "If you'd prefer, I can also connect you with a loan officer for personalized guidance."
        )

    response = AskResponse(
        type=decision.response_type,
        answer=answer,
        recommended_link=recommended_link,
        suggested_next_action=result.get("suggested_next_action") or decision.suggested_next_action,
        display_sources=display_sources,
        meta=ResponseMeta(request_id=request_id),
    )

    # Log detailed retrieval information for debugging and analytics
    logger.info(
        "ask_request",
        extra={
            "request_id": request_id,
            "question": payload.question,
            "response_type": decision.response_type,
            "suggested_next_action": decision.suggested_next_action,
            "display_sources": display_sources,
            "top_k": payload.top_k,
            "used_rag": decision.needs_rag,
            "used_fallback": decision.response_type == "fallback",
            "timestamp": time.time(),
        },
    )
    logging_service.log_ask_request(
        request_id=request_id,
        question=payload.question,
        response_type=decision.response_type,
        answer=answer,
        suggested_next_action=decision.suggested_next_action,
        retrieval_info={
            **logging_service.log_retrieval_debug(
                request_id=request_id,
                question=payload.question,
                matches=matches,
                top_k_requested=payload.top_k,
            ),
            "model_used": settings.openai_model,
            "sources_returned": raw_sources,
            "sources_filtered": display_sources,
            "recommended_link": recommended_link,
        },
    )

    logger.info(
        "ask_debug request_id=%s rag_matches=%s final_decision=%s",
        request_id,
        _match_summary(matches),
        decision.response_type,
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
