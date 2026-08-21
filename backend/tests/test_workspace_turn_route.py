import importlib
import os
import sys
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import cordia_agent, workspace_state


class MemoryStore:
    def __init__(self):
        self.workspace = workspace_state.empty("workspace_1")
        self.artifacts = {"source/memory.md": "Compiled profile memory."}
        self.runs = {}
        self.write_calls = []

    def get_workspace(self, _email, workspace_id):
        return deepcopy(self.workspace) if workspace_id == "workspace_1" else None

    def get_run_by_idempotency(self, _email, workspace_id, key):
        return deepcopy(self.runs.get((workspace_id, key)))

    def get_artifacts(self, _email):
        return deepcopy(self.artifacts)

    def recent_workspace_turns(self, _email, _workspace_id):
        return []

    def commit_workspace_turn(self, _email, workspace_id, expected_revision, key,
                              user_message, public_result, next_state):
        self.write_calls.append((workspace_id, expected_revision, key, user_message))
        prior = self.runs.get((workspace_id, key))
        if prior:
            return {"status": "prior", "result": deepcopy(prior)}
        if workspace_id != "workspace_1":
            return {"status": "missing"}
        if self.workspace["revision"] != expected_revision:
            return {"status": "conflict"}
        self.workspace = deepcopy(next_state)
        self.runs[(workspace_id, key)] = deepcopy(public_result)
        return {"status": "committed", "result": deepcopy(public_result)}


class TestWorkspaceTurnRoute(unittest.TestCase):
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
        self.model_calls = []
        self.runtime = SimpleNamespace(
            cordia_agent=cordia_agent,
            workspace_state=workspace_state,
            store=self.store,
            llm=SimpleNamespace(call=self.call_model),
        )

    def call_model(self, _system, _message, max_tokens):
        self.model_calls.append(max_tokens)
        return '{"kind":"speak","speech":"I can help with that."}'

    def handler(self, body, email="owner@example.test"):
        handler = object.__new__(self.backend.H)
        handler.path = "/surveyor/run"
        handler._body = lambda: deepcopy(body)
        handler._surv_guard = lambda: (email, None)
        handler._json = lambda payload, status=200: setattr(
            handler, "response", (deepcopy(payload), status))
        handler.response = None
        return handler

    def post(self, body, email="owner@example.test"):
        handler = self.handler(body, email)
        with patch.object(self.backend, "surveyor", self.runtime):
            handler.do_POST()
        return handler.response

    def valid(self, **changes):
        value = {"id": "workspace_1", "revision": 0, "message": "Help me plan.",
                 "idempotency_key": "turn_abc123"}
        value.update(changes)
        return value

    def test_invalid_route_request_fails_before_model_or_storage(self):
        response, status = self.post(self.valid(extra="forged"))
        self.assertEqual(status, 400)
        self.assertEqual(response["ok"], False)
        self.assertEqual(self.model_calls, [])
        self.assertEqual(self.store.write_calls, [])

    def test_missing_workspace_and_prior_idempotency_never_call_model(self):
        response, status = self.post(self.valid(id="missing"))
        self.assertEqual((response, status), ({"ok": False, "error": "workspace not found"}, 404))
        self.store.runs[("workspace_1", "turn_abc123")] = {
            "ok": True, "speech": "Prior speech.", "action": None, "revision": 0}
        response, status = self.post(self.valid())
        self.assertEqual((response, status), (self.store.runs[("workspace_1", "turn_abc123")], 200))
        self.assertEqual(self.model_calls, [])
        self.assertEqual(self.store.write_calls, [])

    def test_speak_uses_production_route_and_keeps_the_exact_revision(self):
        response, status = self.post(self.valid())
        self.assertEqual(status, 200)
        self.assertEqual(response, {"ok": True, "speech": "I can help with that.",
                                    "action": None, "revision": 0})
        self.assertEqual(self.model_calls, [700])
        self.assertEqual(self.store.workspace["revision"], 0)
        self.assertEqual(len(self.store.write_calls), 1)

    def test_proposal_commits_one_pending_action_and_one_revision(self):
        def proposal(_system, _message, max_tokens):
            self.model_calls.append(max_tokens)
            return ('{"kind":"propose_connector","speech":"Set it up.","proposal":'
                    '{"connector_id":"issues","display_name":"Issues","setup_kind":"api_key",'
                    '"purpose":"Review issues."}}')
        self.runtime.llm.call = proposal
        response, status = self.post(self.valid())
        self.assertEqual(status, 200)
        self.assertEqual(response["revision"], 1)
        self.assertEqual(response["action"], {"kind": "propose_connector", "state": "setup_required",
                                              "connector_id": "issues", "setup_kind": "api_key"})
        self.assertEqual(self.store.workspace["revision"], 1)
        self.assertEqual(len(self.store.workspace["pending_actions"]), 1)

    def test_model_failure_does_not_write_a_run_or_workspace(self):
        def unavailable(*_args, **_kwargs):
            raise RuntimeError("provider private failure")
        self.runtime.llm.call = unavailable
        response, status = self.post(self.valid())
        self.assertEqual((response, status), ({"ok": False,
                                                "error": "Cordia Agent could not complete that request."}, 502))
        self.assertEqual(self.store.write_calls, [])
        self.assertEqual(self.store.workspace["revision"], 0)


if __name__ == "__main__":
    unittest.main()
