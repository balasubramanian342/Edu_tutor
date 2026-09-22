import unittest
from unittest.mock import patch


class LlmImportsTest(unittest.TestCase):
    def test_llm_package_exposes_compatibility_alias(self):
        from llm import AnthropicLLMClient
        self.assertTrue(callable(AnthropicLLMClient))

    def test_gemini_generate_uses_models_generate_content_api(self):
        from llm.client import GeminiLLMClient

        class FakeModels:
            def __init__(self):
                self.kwargs = None

            def generate_content(self, **kwargs):
                self.kwargs = kwargs
                return type("Response", (), {"text": "Final answer"})()

        class FakeClient:
            def __init__(self):
                self.models = FakeModels()

        with patch("google.genai.Client", return_value=FakeClient()):
            client = GeminiLLMClient(model="gemini-flash-latest", api_key="test-key")
            response = client.generate("system", "user question")

        self.assertEqual(response, "Final answer")
        self.assertIsNotNone(client._client.models.kwargs)
        self.assertEqual(client._client.models.kwargs["model"], "gemini-flash-latest")
        self.assertEqual(client._client.models.kwargs["contents"], "system\n\nuser question")


if __name__ == "__main__":
    unittest.main()
