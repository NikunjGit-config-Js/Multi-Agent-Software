import os
import unittest
from unittest.mock import patch

from orgmind.providers.gemini import GeminiProvider


class GeminiProviderTests(unittest.TestCase):
    @patch("orgmind.providers.gemini.post_json")
    def test_generates_structured_content(self, post_json):
        post_json.return_value = {
            "candidates": [{"content": {"parts": [{"text": '{"tasks": []}'}]}}],
            "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 7},
        }
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            response = GeminiProvider().complete(
                role="ceo",
                system="Plan safely.",
                prompt="Create a plan.",
                json_mode=True,
            )
        self.assertEqual(response.text, '{"tasks": []}')
        self.assertEqual(response.input_tokens, 12)
        self.assertEqual(response.output_tokens, 7)
        url, payload, headers = post_json.call_args.args
        self.assertIn("gemini-2.5-flash:generateContent", url)
        self.assertEqual(payload["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(headers["x-goog-api-key"], "test-key")


if __name__ == "__main__":
    unittest.main()
