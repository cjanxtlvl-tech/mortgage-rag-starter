import unittest

from app.intent_router import route_intent


class RouteIntentTests(unittest.TestCase):
    def test_apply_phrase_routes_to_start_application(self) -> None:
        self.assertEqual(route_intent("I want to apply for a mortgage"), "start_application")

    def test_get_preapproved_phrase_routes_to_start_application(self) -> None:
        self.assertEqual(route_intent("How do I get preapproved?"), "start_application")

    def test_talk_to_someone_phrase_routes_to_loan_officer(self) -> None:
        self.assertEqual(route_intent("Can I talk to someone today?"), "connect_loan_officer")

    def test_get_rates_phrase_routes_to_rates(self) -> None:
        self.assertEqual(route_intent("Can you get rates for me?"), "get_rates")

    def test_general_question_uses_rag_path(self) -> None:
        self.assertIsNone(route_intent("What is debt to income ratio?"))


if __name__ == "__main__":
    unittest.main()
