from typing import Optional


def route_intent(question: str) -> Optional[str]:
    text = question.strip().lower()

    application_triggers = [
        "apply",
        "get preapproved",
        "get pre-approved",
        "pre approved",
        "preapproved",
    ]
    rates_triggers = ["get rates", "rates", "rate quote"]
    handoff_triggers = ["talk to someone", "speak to someone", "loan officer", "talk to a person"]

    if any(trigger in text for trigger in application_triggers):
        return "start_application"
    if any(trigger in text for trigger in rates_triggers):
        return "get_rates"
    if any(trigger in text for trigger in handoff_triggers):
        return "connect_loan_officer"
    return None
