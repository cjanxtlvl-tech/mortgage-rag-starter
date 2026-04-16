"""Unit tests for source filtering and response format."""

import unittest
from uuid import UUID

from app.schemas import AskResponse, ResponseMeta, ResponseType
from app.services.source_filter import is_display_source, filter_sources


class TestSourceFiltering(unittest.TestCase):
    """Test source visibility filtering."""

    def test_public_dataset_visibility(self):
        """Public datasets should be visible."""
        public_sources = [
            "mortgage_basics.json",
            "mortgage_knowledge_base.json",
            "investor_dscr_advanced_dataset.json",
            "mortgage_additional_training.json",
            "mortgage_conversion_dataset.json",
        ]
        for source in public_sources:
            with self.subTest(source=source):
                self.assertTrue(is_display_source(source), f"{source} should be displayable")

    def test_internal_dataset_hidden(self):
        """Internal control datasets should be hidden."""
        internal_sources = [
            "rasa_rag_intent_routing_dataset.json",
            "prompts.json",
            "config.json",
            "settings.json",
            "debug.json",
        ]
        for source in internal_sources:
            with self.subTest(source=source):
                self.assertFalse(is_display_source(source), f"{source} should NOT be displayable")

    def test_hidden_file_patterns(self):
        """Files starting with underscore or dot should be hidden."""
        hidden_patterns = [
            "_internal.json",
            ".config.json",
            ".env",
            "_prompts.json",
        ]
        for source in hidden_patterns:
            with self.subTest(source=source):
                self.assertFalse(is_display_source(source), f"{source} should NOT be displayable")

    def test_internal_keyword_patterns(self):
        """Files with internal keywords should be hidden."""
        internal_keywords = [
            "prompt_template.json",
            "config_mortgage.json",
            "debug_routing.json",
            "internal_control.json",
            "control_dataset.json",
        ]
        for source in internal_keywords:
            with self.subTest(source=source):
                self.assertFalse(is_display_source(source), f"{source} should NOT be displayable")

    def test_case_insensitive_filtering(self):
        """Filtering should be case-insensitive."""
        self.assertTrue(is_display_source("Mortgage_Basics.JSON"))
        self.assertTrue(is_display_source("MORTGAGE_KNOWLEDGE_BASE.json"))
        self.assertFalse(is_display_source("RASA_RAG_INTENT_ROUTING_DATASET.JSON"))

    def test_filter_sources_list(self):
        """filter_sources should remove internal sources from list."""
        mixed_sources = [
            "mortgage_basics.json",
            "rasa_rag_intent_routing_dataset.json",
            "mortgage_knowledge_base.json",
            "prompts.json",
            "investor_dscr_advanced_dataset.json",
        ]
        result = filter_sources(mixed_sources)
        expected = [
            "mortgage_basics.json",
            "mortgage_knowledge_base.json",
            "investor_dscr_advanced_dataset.json",
        ]
        self.assertEqual(result, expected)

    def test_filter_empty_list(self):
        """filter_sources should handle empty lists."""
        result = filter_sources([])
        self.assertEqual(result, [])

    def test_filter_all_internal(self):
        """filter_sources should return empty list if all sources are internal."""
        internal_only = [
            "rasa_rag_intent_routing_dataset.json",
            "prompts.json",
            "_internal.json",
        ]
        result = filter_sources(internal_only)
        self.assertEqual(result, [])


class TestResponseSchema(unittest.TestCase):
    """Test new response schema structure."""

    def test_response_meta_creation(self):
        """ResponseMeta should require request_id."""
        meta = ResponseMeta(request_id="test-123")
        self.assertEqual(meta.request_id, "test-123")

    def test_ask_response_structure(self):
        """AskResponse should have new fields."""
        meta = ResponseMeta(request_id="req-456")
        response = AskResponse(
            type="rag_response",
            answer="This is a test answer",
            suggested_next_action=None,
            display_sources=["mortgage_basics.json"],
            meta=meta,
        )
        self.assertEqual(response.type, "rag_response")
        self.assertEqual(response.answer, "This is a test answer")
        self.assertIsNone(response.suggested_next_action)
        self.assertEqual(response.display_sources, ["mortgage_basics.json"])
        self.assertEqual(response.meta.request_id, "req-456")

    def test_display_sources_default_empty(self):
        """display_sources should default to empty list."""
        meta = ResponseMeta(request_id="req-789")
        response = AskResponse(
            type="start_application",
            answer="Start application answer",
            meta=meta,
        )
        self.assertEqual(response.display_sources, [])

    def test_response_serialization(self):
        """Response should serialize to valid JSON."""
        meta = ResponseMeta(request_id="req-abc")
        response = AskResponse(
            type="rag_response",
            answer="Test answer",
            display_sources=["mortgage_basics.json"],
            meta=meta,
        )
        data = response.model_dump()
        self.assertIn("type", data)
        self.assertIn("answer", data)
        self.assertIn("display_sources", data)
        self.assertIn("meta", data)
        self.assertEqual(data["meta"]["request_id"], "req-abc")


class TestSourceVisibilityEndToEnd(unittest.TestCase):
    """End-to-end tests for source filtering in responses."""

    def test_rag_response_with_mixed_sources(self):
        """RAG response should filter mixed sources."""
        mixed_sources = [
            "mortgage_knowledge_base.json",
            "rasa_rag_intent_routing_dataset.json",
            "_debug.json",
        ]
        filtered = filter_sources(mixed_sources)
        self.assertEqual(filtered, ["mortgage_knowledge_base.json"])
        self.assertNotIn("rasa_rag_intent_routing_dataset.json", filtered)
        self.assertNotIn("_debug.json", filtered)

    def test_routing_response_has_empty_sources(self):
        """Non-RAG routing responses should have empty display_sources."""
        meta = ResponseMeta(request_id="req-xyz")
        response = AskResponse(
            type="start_application",
            answer="Application started",
            suggested_next_action="start_rasa_application",
            display_sources=[],
            meta=meta,
        )
        self.assertEqual(response.display_sources, [])


if __name__ == "__main__":
    unittest.main()
