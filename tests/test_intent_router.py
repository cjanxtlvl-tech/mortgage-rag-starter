import unittest

from app.services.router import classify_user_intent


class RouteIntentTests(unittest.TestCase):
    def test_apply_phrase_routes_to_start_application(self) -> None:
        decision = classify_user_intent("I want to apply for a mortgage")
        self.assertEqual(decision.response_type, "start_application")
        self.assertEqual(decision.suggested_next_action, "start_rasa_application")

    def test_get_preapproved_plus_question_routes_to_rag_then_offer_application(self) -> None:
        decision = classify_user_intent("How much house can I afford and can I get pre-approved?")
        self.assertEqual(decision.response_type, "rag_then_offer_application")
        self.assertEqual(decision.suggested_next_action, "offer_start_rasa_application")
        self.assertTrue(decision.needs_rag)

    def test_talk_to_someone_phrase_routes_to_loan_officer(self) -> None:
        decision = classify_user_intent("Can I talk to a loan officer?")
        self.assertEqual(decision.response_type, "talk_to_loan_officer")
        self.assertEqual(decision.suggested_next_action, "handoff_to_loan_officer")

    def test_get_rates_phrase_routes_to_rates(self) -> None:
        decision = classify_user_intent("Can you share today's rates?")
        self.assertEqual(decision.response_type, "rate_request")
        self.assertEqual(decision.suggested_next_action, "start_rate_flow")

    def test_vague_prompt_routes_to_clarify(self) -> None:
        decision = classify_user_intent("I need help")
        self.assertEqual(decision.response_type, "clarify_goal")
        self.assertEqual(decision.suggested_next_action, "ask_clarifying_question")

    def test_general_question_uses_rag_path(self) -> None:
        decision = classify_user_intent("What is debt to income ratio?")
        self.assertEqual(decision.response_type, "rag_response")
        self.assertTrue(decision.needs_rag)

    def test_non_mortgage_question_routes_to_fallback(self) -> None:
        decision = classify_user_intent("How do I cook pasta?")
        self.assertEqual(decision.response_type, "fallback")
        self.assertIsNone(decision.suggested_next_action)


if __name__ == "__main__":
    unittest.main()
