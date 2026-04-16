from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas import ResponseType

RouteAction = Literal[
    "start_rasa_application",
    "handoff_to_loan_officer",
    "start_rate_flow",
    "offer_start_rasa_application",
    "offer_handoff_to_loan_officer",
    "ask_clarifying_question",
]


@dataclass(frozen=True)
class RouteDecision:
    response_type: ResponseType
    answer: str
    suggested_next_action: RouteAction | None
    needs_rag: bool


def _normalize(text: str) -> str:
    return " ".join(text.lower().split()).strip()


def _contains_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _is_mortgage_related(text: str) -> bool:
    mortgage_terms = [
        "mortgage",
        "home loan",
        "loan",
        "preapproval",
        "pre-approval",
        "preapproved",
        "pre-qualified",
        "prequalified",
        "refinance",
        "refinancing",
        "interest rate",
        "rate",
        "down payment",
        "closing cost",
        "escrow",
        "apr",
        "dscr",
        "debt to income",
        "dti",
        "buy a home",
        "buying a home",
        "buying home",
        "home buying",
        "purchase a home",
        "purchasing a home",
        "first home",
        "first-time buyer",
        "first time buyer",
        "home buyer",
        "homebuyer",
        "home purchase",
        "home ownership",
        "homeownership",
        "house",
        "property",
        "lender",
        "borrower",
        "credit score",
        "qualify",
        "qualification",
        "underwriting",
        "appraisal",
        "title",
        "equity",
        "amortization",
        "pmi",
        "points",
        "origination",
        "afford",
        "budget",
        "process",
    ]
    return _contains_any(text, mortgage_terms)


def _is_education_question(text: str) -> bool:
    education_markers = [
        "what",
        "how",
        "why",
        "when",
        "can i",
        "should i",
        "difference",
        "explain",
        "afford",
        "work",
    ]
    education_topics = [
        "mortgage",
        "pre-approval",
        "preapproval",
        "pre-approved",
        "pre approved",
        "prequalified",
        "refinance",
        "refinancing",
        "dscr",
        "rate",
        "apr",
        "closing cost",
        "loan",
        "home",
        "house",
        "property",
        "afford",
        "buying",
        "purchase",
        "lender",
        "credit",
        "down payment",
        "qualify",
        "step",
        "process",
        "approval",
        "escrow",
        "equity",
        "title",
        "underwriting",
        "appraisal",
    ]
    return _contains_any(text, education_markers) and _contains_any(text, education_topics)


def classify_user_intent(question: str) -> RouteDecision:
    text = _normalize(question)

    clarify_triggers = [
        "i need help",
        "need help",
        "not sure where to start",
        "where do i start",
        "help me",
    ]
    application_triggers = [
        "apply",
        "get started",
        "pre-approved",
        "pre approved",
        "preapproval",
        "pre-approval",
        "prequalified",
        "pre-qualified",
        "buy a home",
        "buying a home",
        "purchase a home",
        "purchasing a home",
        "refinance my mortgage",
        "dscr loan",
    ]
    explicit_application_triggers = [
        "apply",
        "get started",
        "buy a home",
        "refinance my mortgage",
    ]
    officer_triggers = [
        "talk to a loan officer",
        "talk to loan officer",
        "speak with someone",
        "talk to someone",
        "have someone call me",
        "contact me",
        "call me",
    ]
    rate_triggers = [
        "today's rates",
        "todays rates",
        "rate quote",
        "best mortgage rate",
        "what rate can i get",
        "get rates",
        "rates",
    ]

    if _contains_any(text, clarify_triggers):
        return RouteDecision(
            response_type="clarify_goal",
            answer="I can help with mortgage education, rates, or next steps like applying. What would you like to do first?",
            suggested_next_action="ask_clarifying_question",
            needs_rag=False,
        )

    app_intent = _contains_any(text, application_triggers)
    explicit_app_intent = _contains_any(text, explicit_application_triggers)
    officer_intent = _contains_any(text, officer_triggers)
    rate_intent = _contains_any(text, rate_triggers)
    education_intent = _is_education_question(text)
    mortgage_related = _is_mortgage_related(text)
    has_combo_connector = _contains_any(text, [" and ", " also ", " plus "])

    if app_intent and education_intent and has_combo_connector:
        return RouteDecision(
            response_type="rag_then_offer_application",
            answer="",
            suggested_next_action="offer_start_rasa_application",
            needs_rag=True,
        )

    # Educational prompts like "what is a DSCR loan" should stay in RAG.
    if app_intent and education_intent and not explicit_app_intent:
        return RouteDecision(
            response_type="rag_response",
            answer="",
            suggested_next_action=None,
            needs_rag=True,
        )

    if officer_intent and education_intent and has_combo_connector:
        return RouteDecision(
            response_type="rag_then_offer_loan_officer",
            answer="",
            suggested_next_action="offer_handoff_to_loan_officer",
            needs_rag=True,
        )

    if app_intent:
        return RouteDecision(
            response_type="start_application",
            answer="Great. We can begin with a few questions to help match you with the right mortgage path.",
            suggested_next_action="start_rasa_application",
            needs_rag=False,
        )

    if officer_intent:
        return RouteDecision(
            response_type="talk_to_loan_officer",
            answer="Yes. We can connect you with a loan officer for personalized guidance.",
            suggested_next_action="handoff_to_loan_officer",
            needs_rag=False,
        )

    if rate_intent:
        return RouteDecision(
            response_type="rate_request",
            answer="I can help with rate guidance. To provide personalized options, we should start a quick rate request flow.",
            suggested_next_action="start_rate_flow",
            needs_rag=False,
        )

    if mortgage_related:
        return RouteDecision(
            response_type="rag_response",
            answer="",
            suggested_next_action=None,
            needs_rag=True,
        )

    return RouteDecision(
        response_type="fallback",
        answer="I can currently help with mortgage and home-loan questions. If you share your mortgage goal, I can guide your next step.",
        suggested_next_action=None,
        needs_rag=False,
    )
