import unittest

from app.rag.pipeline import APPLICATION_CTA, _assemble_answer


class PipelineCtaAssemblyTests(unittest.TestCase):
    def test_appends_application_cta_once_when_requested(self) -> None:
        answer = _assemble_answer("DSCR compares income to debt payments.", include_application_cta=True)

        self.assertTrue(answer.endswith(APPLICATION_CTA))
        self.assertEqual(answer.count(APPLICATION_CTA), 1)

    def test_dedupes_cta_like_paragraphs(self) -> None:
        answer = _assemble_answer(
            "DSCR compares income to debt payments.\n\n"
            "If you'd like, we can start ashort application flow to match you with the right mortgage path.\n\n"
            "If you'd like, we can start a short application flow to match you with the right mortgage path.",
            include_application_cta=True,
        )

        self.assertEqual(answer.count(APPLICATION_CTA), 1)
        self.assertIn("DSCR compares income to debt payments.", answer)

    def test_does_not_append_cta_when_not_requested(self) -> None:
        answer = _assemble_answer("DSCR compares income to debt payments.", include_application_cta=False)

        self.assertEqual(answer, "DSCR compares income to debt payments.")


if __name__ == "__main__":
    unittest.main()