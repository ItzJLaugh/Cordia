import io
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class TestCredentialedCors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = tempfile.TemporaryDirectory(prefix="cordia-cors-test-")
        auth_stub = types.ModuleType("cordia_auth")
        with patch.dict(os.environ, {"CORDIA_CORPUS_DIR": cls.corpus.name}), \
                patch.dict(sys.modules, {"cordia_auth": auth_stub}):
            import training_backend
        cls.backend = training_backend

    @classmethod
    def tearDownClass(cls):
        cls.corpus.cleanup()

    def _response(self, origin):
        backend = self.backend

        class ResponseHarness:
            _cors = backend.H._cors

            def __init__(self):
                self.headers = {"Origin": origin}
                self.response_code = None
                self.response_headers = []
                self.wfile = io.BytesIO()

            def send_response(self, code):
                self.response_code = code

            def send_header(self, name, value):
                self.response_headers.append((name, value))

            def end_headers(self):
                pass

        return ResponseHarness()

    def test_exact_local_origin_gets_credentials_on_preflight_and_actual_response_only(self):
        allowed = "http://127.0.0.1:8000"
        unknown = "http://attacker.example:8000"

        for origin, should_allow in ((allowed, True), (unknown, False)):
            with self.subTest(origin=origin, response="preflight"):
                response = self._response(origin)
                self.backend.H.do_OPTIONS(response)
                headers = dict(response.response_headers)
                self.assertEqual(response.response_code, 204)
                self.assertEqual(headers.get("Vary"), "Origin")
                self.assertEqual(headers.get("Access-Control-Allow-Origin"),
                                 origin if should_allow else None)
                self.assertEqual(headers.get("Access-Control-Allow-Credentials"),
                                 "true" if should_allow else None)

            with self.subTest(origin=origin, response="actual"):
                response = self._response(origin)
                self.backend.H._json(response, {"ok": True})
                headers = dict(response.response_headers)
                self.assertEqual(response.response_code, 200)
                self.assertEqual(headers.get("Vary"), "Origin")
                self.assertEqual(headers.get("Access-Control-Allow-Origin"),
                                 origin if should_allow else None)
                self.assertEqual(headers.get("Access-Control-Allow-Credentials"),
                                 "true" if should_allow else None)
                self.assertEqual(response.wfile.getvalue(), b'{"ok": true}')


if __name__ == "__main__":
    unittest.main()
