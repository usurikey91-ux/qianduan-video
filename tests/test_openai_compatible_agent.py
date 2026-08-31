import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sau_backend
from backend_app.agent.openai_compatible_client import (
    openai_compatible_request,
    public_universal_ai_settings,
    universal_ai_completion,
)
from backend_app.agent.structured_runner import call_universal_ai_structured


class OpenAICompatibleAgentTests(unittest.TestCase):
    def test_public_settings_never_return_api_key(self):
        public = public_universal_ai_settings({
            "universalAI": {
                "providerName": "测试厂商",
                "protocol": "openai-compatible",
                "baseUrl": "https://relay.example/v1",
                "apiKey": "secret-value",
                "timeout": 120,
            }
        })
        self.assertTrue(public["apiKeyConfigured"])
        self.assertNotIn("apiKey", public)

    @patch("backend_app.agent.openai_compatible_client.urllib.request.urlopen")
    def test_request_uses_non_urllib_user_agent(self, urlopen_mock):
        response = urlopen_mock.return_value.__enter__.return_value
        response.read.return_value = b'{"data":[]}'
        result = openai_compatible_request(
            "/models",
            settings={"openaiCompatible": {"baseUrl": "https://relay.example/v1", "apiKey": "secret"}},
        )
        self.assertEqual({"data": []}, result)
        request = urlopen_mock.call_args.args[0]
        self.assertNotIn("Python-urllib", request.get_header("User-agent"))
        self.assertIn("ContentWorkbench", request.get_header("User-agent"))

    @patch("backend_app.agent.openai_compatible_client.openai_compatible_request")
    def test_structured_runner_accepts_openai_compatible_response(self, request_mock):
        request_mock.return_value = {
            "choices": [{"message": {"content": '{"result":"OK"}'}}]
        }
        result = call_universal_ai_structured(
            "test",
            {"type": "object"},
            settings={
                "universalAI": {
                    "protocol": "openai-compatible",
                    "baseUrl": "https://relay.example/v1",
                    "apiKey": "secret-value",
                }
            },
            model_config={
                "provider": "openai-compatible",
                "model": "gpt-5.6-sol",
                "reasoningEffort": "high",
            },
        )
        self.assertEqual({"result": "OK"}, result)
        payload = request_mock.call_args.kwargs["payload"]
        self.assertEqual("gpt-5.6-sol", payload["model"])
        self.assertEqual("high", payload["reasoning_effort"])

    @patch("backend_app.agent.openai_compatible_client._json_request")
    def test_anthropic_native_protocol_is_adapted(self, request_mock):
        request_mock.return_value = {"content": [{"type": "text", "text": '{"result":"OK"}'}]}
        content = universal_ai_completion(
            [{"role": "system", "content": "system"}, {"role": "user", "content": "hello"}],
            settings={"universalAI": {
                "protocol": "anthropic", "baseUrl": "https://api.anthropic.com/v1", "apiKey": "secret"
            }},
            model_config={"model": "claude-test"},
        )
        self.assertEqual('{"result":"OK"}', content)
        self.assertTrue(request_mock.call_args.args[0].endswith("/v1/messages"))
        self.assertEqual("secret", request_mock.call_args.kwargs["headers"]["x-api-key"])

    @patch("backend_app.agent.openai_compatible_client._json_request")
    def test_gemini_native_protocol_is_adapted(self, request_mock):
        request_mock.return_value = {"candidates": [{"content": {"parts": [{"text": '{"result":"OK"}'}]}}]}
        content = universal_ai_completion(
            [{"role": "system", "content": "system"}, {"role": "user", "content": "hello"}],
            settings={"universalAI": {
                "protocol": "gemini", "baseUrl": "https://generativelanguage.googleapis.com/v1beta", "apiKey": "secret"
            }},
            model_config={"model": "gemini-test"},
        )
        self.assertEqual('{"result":"OK"}', content)
        self.assertIn("/models/gemini-test:generateContent", request_mock.call_args.args[0])
        self.assertEqual("secret", request_mock.call_args.kwargs["headers"]["x-goog-api-key"])

    def test_settings_endpoint_saves_secret_locally_and_selects_model(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_path = Path(tmp_dir) / "settings.json"
            with patch.object(sau_backend, "get_settings_path", return_value=settings_path):
                response = sau_backend.app.test_client().put(
                    "/settings/universal-ai",
                    json={
                        "providerName": "测试中转站",
                        "protocol": "openai-compatible",
                        "baseUrl": "https://relay.example/v1",
                        "apiKey": "secret-value",
                        "model": "gpt-5.6-sol",
                        "timeout": 300,
                    },
                )
                payload = response.get_json()
                self.assertEqual(200, response.status_code)
                self.assertNotIn("apiKey", payload["data"])
                self.assertTrue(payload["data"]["apiKeyConfigured"])
                saved = json.loads(settings_path.read_text(encoding="utf-8"))
                self.assertEqual("secret-value", saved["universalAI"]["apiKey"])
                self.assertEqual("universal-ai-default", saved["taskModels"]["viralAnalysis"])
                model = next(item for item in saved["agentModels"] if item["id"] == "universal-ai-default")
                self.assertEqual("gpt-5.6-sol", model["model"])


if __name__ == "__main__":
    unittest.main()
