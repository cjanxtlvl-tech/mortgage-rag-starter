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
    keywords = [
        "mortgage", "loan", "home", "house", "refinance", "rate",
        "pre approval", "pre-approval", "prequal", "pre-qualify",
        "prequalification", "credit", "dscr", "fha", "va loan",
        "pre approval credit", "credit check mortgage"
    ]
    return any(keyword in text.lower() for keyword in keywords)


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


import logging

logger = logging.getLogger(__name__)

def classify_user_intent(question: str) -> RouteDecision:
    # Detect features indicating high purchase intent
    personal_details = any(keyword in question.lower() for keyword in ["credit score", "down payment", "qualify", "loan", "mortgage"])
    purchase_intent = any(keyword in question.lower() for keyword in ["buy", "purchase", "home", "house"])
    comparison_intent = any(keyword in question.lower() for keyword in ["fha", "conventional", "best", "options"])

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
    # Determine response type based on detected features
    response_type = None
    suggested_next_action = None

    if personal_details and (purchase_intent or comparison_intent):
        response_type = "rag_then_offer_application"
        suggested_next_action = "offer_start_rasa_application"
    elif purchase_intent:
        response_type = "talk_to_loan_officer"
        suggested_next_action = "handoff_to_loan_officer"

    logger.debug(
        "intent_features",
        extra={
            "personal_details": personal_details,
            "purchase_intent": purchase_intent,
            "comparison_intent": comparison_intent,
            "response_type": response_type,
            "suggested_next_action": suggested_next_action,
            "classification": "educational" if education_intent else "scenario/high-intent" if personal_details else "fallback/out-of-domain",
        },
    )
    logger.debug(f"Detected features - Personal Details: {personal_details}, Purchase Intent: {purchase_intent}, Comparison Intent: {comparison_intent}")

    # Determine response type based on detected features
    if personal_details and (purchase_intent or comparison_intent):
        return RouteDecision(
            response_type="rag_then_offer_application",
            answer="",
            suggested_next_action="offer_start_rasa_application",
            needs_rag=True,
        )
    elif purchase_intent:
        return RouteDecision(
            response_type="talk_to_loan_officer",
            answer="Yes. We can connect you with a loan officer for personalized guidance.",
            suggested_next_action="handoff_to_loan_officer",
            needs_rag=False,
        )

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

    # Educational queries with potential conversion intent
    if education_intent and mortgage_related:
        if any(phrase in text for phrase in ["does", "will", "how", "what", "can i qualify"]):
            return RouteDecision(
                response_type="rag_then_offer_application",
                answer="",
                suggested_next_action="offer_start_rasa_application",
                needs_rag=True,
            )
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

    # Document-related questions should provide educational response first
    document_related = any(keyword in question.lower() for keyword in ["documents", "paperwork", "required documents", "application documents"])

    if document_related:
        return RouteDecision(
            response_type="rag_then_offer_application",
            answer="To apply for a mortgage, you'll typically need documents like proof of income, tax returns, and bank statements. If you're ready, we can start the application process.",
            suggested_next_action="offer_start_rasa_application",
            needs_rag=True,
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

    if mortgage_related or _is_mortgage_related(text):
        return RouteDecision(
            response_type="rag_response",
            answer="",
            suggested_next_action=None,
            needs_rag=True,
        )

    if any(phrase in text for phrase in ["can i", "does it", "will it"]) and mortgage_related:
        return RouteDecision(
            response_type="rag_then_offer_application",
            answer="",
            suggested_next_action="offer_start_rasa_application",
            needs_rag=True,
        )

    return RouteDecision(
        response_type="fallback",
        answer="I can currently help with mortgage and home-loan questions. If you share your mortgage goal, I can guide your next step.",
        suggested_next_action=None,
        needs_rag=False,
    )

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

    # Educational queries with potential conversion intent
    if education_intent and mortgage_related:
        if any(phrase in text for phrase in ["does", "will", "how", "what", "can i qualify"]):
            return RouteDecision(
                response_type="rag_then_offer_application",
                answer="",
                suggested_next_action="offer_start_rasa_application",
                needs_rag=True,
            )
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

    # Direct application intent
    if explicit_app_intent:
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

    if mortgage_related or _is_mortgage_related(text):
        return RouteDecision(
            response_type="rag_response",
            answer="",
            suggested_next_action=None,
            needs_rag=True,
        )

    if any(phrase in text for phrase in ["can i", "does it", "will it"]) and mortgage_related:
        return RouteDecision(
            response_type="rag_then_offer_application",
            answer="",
            suggested_next_action="offer_start_rasa_application",
            needs_rag=True,
        )

    return RouteDecision(
        response_type="fallback",
        answer="I can currently help with mortgage and home-loan questions. If you share your mortgage goal, I can guide your next step.",
        suggested_next_action=None,
        needs_rag=False,
    )
