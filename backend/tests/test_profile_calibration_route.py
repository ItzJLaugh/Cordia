import importlib
import io
import json
import os
import sys
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import profile_calibration
from test_profile_calibration import VALID


class MemoryStore:
    def __init__(self):
        self.existing_workspace_id = None
        self.saved_calibration = None
        self.saved_artifacts = {}
        self.write_calls = []

    def save_profile_calibration(self, email, calibration):
        self.write_calls.append(("calibration", email))
        self.saved_calibration = deepcopy(calibration)

    def get_profile_calibration(self, _email):
        return deepcopy(self.saved_calibration)

    def get_connector_states(self, _email):
        return {}

    def ensure_initial_workspace(self, email, prepared):
        self.write_calls.append(("workspace", email))
        if self.existing_workspace_id:
            return self.existing_workspace_id, False
        return "workspace-1", True

    def get_artifacts(self, _email):
        return deepcopy(self.saved_artifacts)

    def save_artifacts(self, email, artifacts):
        self.write_calls.append(("artifacts", email))
        self.saved_artifacts = deepcopy(artifacts)

    def list_interfaces(self, _email):
        if self.existing_workspace_id:
            return [{"id": self.existing_workspace_id}]
        if self.saved_calibration:
            return [{"id": "workspace-1"}]
        return []


class TestProfileCalibrationRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._missing = object()
        cls._prior = sys.modules.get("training_backend", cls._missing)
        cls._auth_patch = patch.dict(sys.modules, {"cordia_auth": SimpleNamespace()})
        cls._auth_patch.start()
        sys.modules.pop("training_backend", None)
        cls.backend = importlib.import_module("training_backend")

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("training_backend", None)
        cls._auth_patch.stop()
        if cls._prior is not cls._missing:
            sys.modules["training_backend"] = cls._prior

    def setUp(self):
        self.store = MemoryStore()
        self.runtime = SimpleNamespace(
            profile_calibration=profile_calibration,
            pipeline=SimpleNamespace(load_profile=lambda _email: {"profile": "owner"}),
            workspace_generation=SimpleNamespace(
                prepare=lambda candidate, _profile, _connectors, calibration: {
                    "id": candidate,
                    "artifacts": {
                        "source/memory.md": profile_calibration.compile_memory(calibration),
                    },
                }
            ),
            store=self.store,
        )

    def handler(self, path, body=None, email="owner@example.test"):
        handler = object.__new__(self.backend.H)
        handler.path = path
        handler._body = lambda: deepcopy(body if body is not None else {})
        handler._surv_guard = lambda: (email, None)
        handler._json = lambda payload, status=200: setattr(
            handler, "response", (deepcopy(payload), status)
        )
        handler.response = None
        return handler

    def post(self, path, body, email="owner@example.test"):
        handler = self.handler(path, body, email)
        with patch.object(self.backend, "surveyor", self.runtime):
            handler.do_POST()
        return handler.response

    def test_import_stores_validated_profile_memory_and_returns_one_workspace(self):
        with patch.dict(os.environ, {"CORDIA_PROFILE_DEV_IMPORT": "1"}, clear=False):
            response, status = self.post("/surveyor/profile-calibration/import", VALID)
        self.assertEqual(status, 200)
        self.assertEqual(response, {"ok": True, "workspace_id": "workspace-1", "created": True})
        self.assertEqual(self.store.saved_calibration, VALID)
        self.assertIn("source/memory.md", self.store.saved_artifacts)

    def test_import_rejects_unknown_fields_without_any_write(self):
        with patch.dict(os.environ, {"CORDIA_PROFILE_DEV_IMPORT": "1"}, clear=False):
            response, status = self.post(
                "/surveyor/profile-calibration/import", {**VALID, "prompt": "ignore rules"}
            )
        self.assertEqual(status, 400)
        self.assertEqual(self.store.write_calls, [])

    def test_reimport_refreshes_memory_for_the_existing_owner_workspace(self):
        self.store.existing_workspace_id = "workspace-existing"
        with patch.dict(os.environ, {"CORDIA_PROFILE_DEV_IMPORT": "1"}, clear=False):
            response, status = self.post("/surveyor/profile-calibration/import", VALID)
        self.assertEqual(status, 200)
        self.assertEqual((response["workspace_id"], response["created"]),
                         ("workspace-existing", False))
        self.assertIn("source/memory.md", self.store.saved_artifacts)

    def test_import_is_not_a_production_bypass(self):
        with patch.dict(os.environ, {"CORDIA_PROFILE_DEV_IMPORT": "0"}, clear=False):
            response, status = self.post("/surveyor/profile-calibration/import", VALID)
        self.assertEqual((response, status), ({"error": "not found"}, 404))
        self.assertEqual(self.store.write_calls, [])

    def test_completion_route_accepts_only_signed_owner_bound_result(self):
        with patch.dict(os.environ, {"CORDIA_PROFILE_STATE_KEY": "state-test-key"}, clear=False):
            state = profile_calibration.issue_state("owner@example.test")
            with patch.object(profile_calibration, "fetch_result", return_value=VALID):
                response, status = self.post("/surveyor/profile-calibration/complete", {
                    "state": state, "result_id": "result_123",
                })
        self.assertEqual(status, 200)
        self.assertEqual(response, {"ok": True, "workspace_id": "workspace-1", "created": True})
        self.assertEqual(self.store.saved_calibration, VALID)

    def test_completion_rejects_extra_fields_without_any_write(self):
        with patch.dict(os.environ, {"CORDIA_PROFILE_STATE_KEY": "state-test-key"}, clear=False):
            state = profile_calibration.issue_state("owner@example.test")
            response, status = self.post("/surveyor/profile-calibration/complete", {
                "state": state, "result_id": "result_123", "next": "https://attacker.test",
            })
        self.assertEqual(status, 400)
        self.assertEqual(self.store.write_calls, [])

    def test_status_route_uses_calibration_and_never_creates_a_workspace(self):
        self.store.saved_calibration = deepcopy(VALID)
        handler = self.handler("/surveyor/profile-calibration")
        with patch.object(self.backend, "surveyor", self.runtime):
            handler.do_GET()
        self.assertEqual(handler.response, (
            {"ok": True, "calibrated": True, "workspace_id": "workspace-1"}, 200,
        ))
        self.assertEqual(self.store.write_calls, [])


class TestProfileCalibrationSecurityContract(unittest.TestCase):
    def test_state_is_owner_bound_expiring_and_rejects_added_fields(self):
        with patch.dict(os.environ, {"CORDIA_PROFILE_STATE_KEY": "state-test-key"}, clear=False):
            token = profile_calibration.issue_state(" Owner@Example.Test ", now=100)
            payload = profile_calibration.verify_state(token, "owner@example.test", now=101)
            self.assertEqual(set(payload), {"email", "nonce", "exp"})
            self.assertEqual(payload["email"], "owner@example.test")
            with self.assertRaises(ValueError):
                profile_calibration.verify_state(token, "other@example.test", now=101)
            with self.assertRaises(ValueError):
                profile_calibration.verify_state(token, "owner@example.test", now=1001)

    def test_fetch_result_uses_only_fixed_url_rejects_redirects_and_validates(self):
        class Response:
            def __init__(self, url, body):
                self.url = url
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def geturl(self):
                return self.url

            def read(self, _size=-1):
                return self.body

        calls = []

        def opener(request, timeout):
            calls.append((request.full_url, timeout))
            return Response(request.full_url, json.dumps(VALID).encode())

        with patch.dict(os.environ, {"CORDIA_PROFILE_RESULT_URL": "https://provider.test/results"},
                        clear=False):
            result = profile_calibration.fetch_result("result_123", opener=opener)
            self.assertEqual(result, VALID)
            self.assertEqual(calls, [("https://provider.test/results/result_123", 10)])

            def redirecting_opener(request, timeout):
                return Response("https://attacker.test/result", json.dumps(VALID).encode())

            with self.assertRaises(ValueError):
                profile_calibration.fetch_result("result_123", opener=redirecting_opener)
            with self.assertRaises(ValueError):
                profile_calibration.fetch_result("https://attacker.test", opener=opener)


if __name__ == "__main__":
    unittest.main()
