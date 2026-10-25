import json
import httpx
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import (
    ProviderAPIError,
    _GEMINI_MODEL,
    _friendly_provider_error,
    analyze_with_gemini,
    analyze_with_openrouter,
    app,
)


class StartupAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_home_page_renders(self):
        with patch("app.load_dotenv"), patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "", "OPENROUTER_API_KEY": ""},
            clear=True,
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Startup Idea Analyzer", response.data)

    def test_short_idea_is_rejected(self):
        response = self.client.post("/api/analyze", json={"idea": "too short"})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"more detailed description", response.data)

    def test_missing_api_keys_return_setup_message(self):
        with patch("app.load_dotenv"), patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "", "OPENROUTER_API_KEY": ""},
            clear=True,
        ):
            response = self.client.post(
                "/api/analyze",
                json={"idea": "A detailed idea for a local delivery service."},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn(b"No AI provider is configured", response.data)

    def test_gemini_key_is_read_from_environment(self):
        analysis = {
            "uniqueness": "Distinctive.",
            "competition": "Some competition.",
            "goToMarketStrategy": "Start locally.",
            "feasibilityScore": 7,
            "overallAssessment": "Worth validating.",
        }
        idea = "A detailed idea for a local delivery service."

        with patch("app.load_dotenv"), patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-gemini-key", "OPENROUTER_API_KEY": ""},
            clear=True,
        ), patch("app.analyze_with_gemini", return_value=analysis) as analyze:
            response = self.client.post("/api/analyze", json={"idea": idea})

        self.assertEqual(response.status_code, 200)
        analyze.assert_called_once_with(idea, "test-gemini-key")

    def test_gemini_uses_supported_model(self):
        analysis = {
            "uniqueness": "Distinctive.",
            "competition": "Some competition.",
            "goToMarketStrategy": "Start locally.",
            "feasibilityScore": 7,
            "overallAssessment": "Worth validating.",
        }
        client = SimpleNamespace(
            models=SimpleNamespace(
                generate_content=Mock(
                    return_value=SimpleNamespace(text=json.dumps(analysis))
                )
            )
        )

        with patch("google.genai.Client", return_value=client) as client_factory:
            result = analyze_with_gemini("A useful startup idea.", "test-key")

        client_factory.assert_called_once_with(api_key="test-key")
        client.models.generate_content.assert_called_once()
        self.assertEqual(
            client.models.generate_content.call_args.kwargs["model"],
            _GEMINI_MODEL,
        )
        self.assertEqual(result, analysis)

    def test_gemini_model_constant_matches_supported_api_name(self):
        """Verify the model constant matches the name Google's API actually lists.

        This test makes a real API call using the key in .env.  It is skipped
        automatically when GEMINI_API_KEY is not set so CI remains green.
        """
        import unittest
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            self.skipTest("GEMINI_API_KEY not set — skipping live API check")

        from google import genai
        client = genai.Client(api_key=key)
        model_names = {m.name for m in client.models.list()}
        # The API returns names prefixed with "models/", e.g. "models/gemini-3.8-flash"
        expected_name = f"models/{_GEMINI_MODEL}"
        self.assertIn(
            expected_name,
            model_names,
            f"Model '{_GEMINI_MODEL}' was not found in the API model list. "
            f"Update _GEMINI_MODEL in app.py to a supported model.",
        )

    def test_openrouter_uses_configured_key_as_bearer_token(self):
        analysis = {
            "uniqueness": "Distinctive.",
            "competition": "Some competition.",
            "goToMarketStrategy": "Start locally.",
            "feasibilityScore": 7,
            "overallAssessment": "Worth validating.",
        }
        response = Mock(status_code=200)
        response.json.return_value = {
            "choices": [{"message": {"content": json.dumps(analysis)}}]
        }

        with patch("app.requests.post", return_value=response) as post:
            result = analyze_with_openrouter("A useful startup idea.", "test-openrouter-key")

        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-openrouter-key",
        )
        self.assertEqual(result, analysis)

    def test_network_errors_get_a_friendly_message(self):
        error = httpx.ConnectError("Connection details should stay private.")
        message, status = _friendly_provider_error("Google Gemini", error, None, str(error))

        self.assertEqual(status, 503)
        self.assertIn("Could not connect", message)
        self.assertNotIn("Connection details", message)

    def test_invalid_api_key_gets_a_friendly_message(self):
        message, status = _friendly_provider_error(
            "Google Gemini",
            ProviderAPIError(403, "Invalid API key."),
            403,
            "Invalid API key.",
        )

        self.assertEqual(status, 502)
        self.assertIn("API key was rejected", message)

    def test_provider_details_are_not_returned_to_the_browser(self):
        secret_marker = "test-key-do-not-expose"
        with patch("app.load_dotenv"), patch.dict(
            os.environ,
            {"GEMINI_API_KEY": secret_marker, "OPENROUTER_API_KEY": ""},
            clear=True,
        ), patch(
            "app.analyze_with_gemini",
            side_effect=ProviderAPIError(404, f"Model response included {secret_marker}"),
        ):
            response = self.client.post(
                "/api/analyze",
                json={"idea": "A detailed idea for a local delivery service."},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn(b"selected AI model is unavailable", response.data)
        self.assertNotIn(secret_marker.encode(), response.data)
        self.assertNotIn(b"Model response included", response.data)


if __name__ == "__main__":
    unittest.main()
