import json
import os
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import model_provider


class FakeResponse:
    def __init__(self, body, url):
        self._body = body
        self._url = url

    def read(self, size=-1):
        return self._body if size < 0 else self._body[:size]

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeOpener:
    def __init__(self, response, *, url="https://model.example.test/v1/chat/completions"):
        self.response = FakeResponse(json.dumps(response).encode("utf-8"), url)
        self.timeout = None
        self.public_trace = {}

    def __call__(self, request, timeout):
        self.timeout = timeout
        self.public_trace = {
            "url": request.full_url,
            "body": json.loads(request.data.decode("utf-8")),
        }
        return self.response


@contextmanager
def configured_provider(**values):
    config = {
        "LLM_BASE_URL": "https://model.example.test/v1/chat/completions",
        "LLM_MODEL": "cordia-test-model",
        "LLM_KEY": "test-secret",
    }
    config.update(values)
    with patch.dict(os.environ, config, clear=True):
        yield


class TestModelProvider(unittest.TestCase):
    def fail_opener(self, *args, **kwargs):
        self.fail("missing configuration must not contact the provider")

    def test_missing_key_is_unavailable_and_never_calls_network(self):
        with patch.dict(os.environ, {"LLM_KEY": ""}, clear=True):
            with self.assertRaisesRegex(model_provider.ModelUnavailable,
                                        "^Cordia Agent is not configured\\.$"):
                model_provider.call("system", "user", opener=self.fail_opener)

    def test_valid_response_returns_only_assistant_content(self):
        opener = FakeOpener({"choices": [{"message": {"content": "Hello"}}]})
        with configured_provider():
            self.assertEqual(model_provider.call("system", "user", opener=opener), "Hello")
        self.assertEqual(opener.timeout, 30)
        self.assertEqual(opener.public_trace["body"], {
            "model": "cordia-test-model",
            "messages": [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            "max_tokens": 900,
            "temperature": 0.4,
        })
        self.assertNotIn("test-secret", repr(opener.public_trace))

    def test_malformed_or_failed_provider_never_falls_back_to_fake_speech(self):
        for response in ({}, {"choices": []}, {"choices": [{"message": {"content": ""}}]}):
            with self.subTest(response=response), configured_provider():
                with self.assertRaisesRegex(model_provider.ModelFailure,
                                            "^Cordia Agent could not complete that request\\.$"):
                    model_provider.call("system", "user", opener=FakeOpener(response))

    def test_cross_origin_redirect_is_a_public_provider_failure(self):
        opener = FakeOpener({"choices": [{"message": {"content": "Hello"}}]},
                            url="https://redirected.example.test/answer")
        with configured_provider():
            with self.assertRaisesRegex(model_provider.ModelFailure,
                                        "^Cordia Agent could not complete that request\\.$"):
                model_provider.call("system", "user", opener=opener)

    def test_non_https_or_credentialed_origin_is_unavailable_without_network(self):
        for base_url in (
            "http://model.example.test/v1/chat/completions",
            "https://key@model.example.test/v1/chat/completions",
        ):
            with self.subTest(base_url=base_url), configured_provider(LLM_BASE_URL=base_url):
                with self.assertRaisesRegex(model_provider.ModelUnavailable,
                                            "^Cordia Agent provider configuration is invalid\\.$"):
                    model_provider.call("system", "user", opener=self.fail_opener)

    def test_oversized_response_is_a_public_provider_failure(self):
        opener = FakeOpener({"choices": [{"message": {"content": "Hello"}}]})
        opener.response = FakeResponse(b"x" * (256 * 1024 + 1),
                                       "https://model.example.test/v1/chat/completions")
        with configured_provider():
            with self.assertRaisesRegex(model_provider.ModelFailure,
                                        "^Cordia Agent could not complete that request\\.$"):
                model_provider.call("system", "user", opener=opener)

    def test_prompts_and_requested_tokens_are_bounded_before_the_network_call(self):
        opener = FakeOpener({"choices": [{"message": {"content": "Hello"}}]})
        with configured_provider():
            model_provider.call("s" * 12_001, "u" * 12_001,
                                max_tokens=120_000, opener=opener)
        body = opener.public_trace["body"]
        self.assertEqual(len(body["messages"][0]["content"]), 12_000)
        self.assertEqual(len(body["messages"][1]["content"]), 12_000)
        self.assertEqual(body["max_tokens"], 1_200)


if __name__ == "__main__":
    unittest.main()
