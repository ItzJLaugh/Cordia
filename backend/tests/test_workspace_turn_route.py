import importlib
import json
import os
import sys
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import artifacts, cordia_agent, workspace_state


class MemoryStore:
    def __init__(self):
        self.workspace = workspace_state.empty("workspace_1")
        self.artifacts = {"source/memory.md": "Compiled profile memory."}
        self.runs = {}
        self.write_calls = []
        self.workspace_read = None
        self.workspace_listing = None
        self.connector_states = {}
        self.interfaces = {"workspace_1": {"id": "workspace_1"}}
        self.mutation_status = None
        self.save_status = None
        self.interface_transaction_status = None
        self.connector_transaction_status = None

    def get_workspace(self, _email, workspace_id):
        if workspace_id != "workspace_1":
            return None
        return deepcopy(self.workspace_read if self.workspace_read is not None else self.workspace)

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

    def save_workspace(self, _email, workspace_id, state, expected_revision):
        if self.save_status:
            return {"status": self.save_status, "workspace": deepcopy(self.workspace)}
        if workspace_id != "workspace_1" or self.workspace["revision"] != expected_revision:
            return {"status": "conflict", "workspace": deepcopy(self.workspace)}
        saved = deepcopy(state)
        saved["revision"] = expected_revision + 1
        self.workspace = saved
        return {"status": "saved", "workspace": deepcopy(saved)}

    def mutate_workspace(self, _email, workspace_id, mutate):
        if self.mutation_status:
            return {"status": self.mutation_status, "workspace": deepcopy(self.workspace)}
        if workspace_id != "workspace_1":
            return {"status": "missing"}
        changed = mutate(deepcopy(self.workspace))
        changed["revision"] = self.workspace["revision"] + 1
        self.workspace = deepcopy(changed)
        return {"status": "saved", "workspace": deepcopy(self.workspace)}

    def workspaces(self, _email):
        return deepcopy(self.workspace_listing if self.workspace_listing is not None
                        else [("workspace_1", self.workspace)])

    def get_connector_states(self, _email):
        return deepcopy(self.connector_states)

    def save_connector_states(self, _email, states):
        self.connector_states = deepcopy(states)

    def get_interface(self, _email, workspace_id):
        return deepcopy(self.interfaces.get(workspace_id))

    def save_interface(self, _email, existing, _name, _description, _definition, _theme):
        return existing or "workspace_1"

    def save_interface_projection(self, _email, workspace_id, name, description, definition,
                                  _theme, _connector_states=None):
        if self.interface_transaction_status:
            return {"status": self.interface_transaction_status}
        self.workspace = workspace_state.merge_interface(
            self.workspace, {**definition, "name": name, "description": description})
        self.workspace["revision"] += 1
        return {"status": "committed", "id": workspace_id,
                "workspace": deepcopy(self.workspace)}

    def save_connector_projection(self, _email, states, secret=None, runtime_status=None):
        if self.connector_transaction_status:
            return {"status": self.connector_transaction_status}
        self.connector_states = deepcopy(states)
        self.workspace = workspace_state.refresh_connectors(self.workspace, states)
        if runtime_status:
            self.workspace = workspace_state.record_connector_runtime(
                self.workspace, "github", runtime_status)
        self.workspace["revision"] += 1
        return {"status": "committed", "connector_states": deepcopy(self.connector_states),
                "workspace_ids": ["workspace_1"]}

    def save_connector_runtime_projection(self, _email, connector_id, runtime_status):
        if self.connector_transaction_status:
            return {"status": self.connector_transaction_status}
        self.workspace = workspace_state.record_connector_runtime(
            self.workspace, connector_id, runtime_status)
        self.workspace["revision"] += 1
        return {"status": "committed", "workspace_ids": ["workspace_1"]}

    def log_event(self, *_args, **_kwargs):
        return None


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
            artifacts=artifacts,
            pipeline=SimpleNamespace(artifact_bundle=lambda _email: {}),
        )

    def call_model(self, _system, _message, max_tokens):
        self.model_calls.append(max_tokens)
        return '{"kind":"speak","speech":"I can help with that."}'

    def handler(self, body, email="owner@example.test", path="/surveyor/run"):
        handler = object.__new__(self.backend.H)
        handler.path = path
        handler._body = lambda: deepcopy(body)
        handler._surv_guard = lambda: (email, None)
        handler._json = lambda payload, status=200: setattr(
            handler, "response", (deepcopy(payload), status))
        handler.response = None
        return handler

    def post(self, body, email="owner@example.test", path="/surveyor/run"):
        handler = self.handler(body, email, path)
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

    def test_turn_revision_conflict_uses_the_exact_dashboard_contract(self):
        self.store.workspace["revision"] = 1
        response, status = self.post(self.valid())
        self.assertEqual((response, status),
                         ({"ok": False, "error": "revision_conflict"}, 409))

    def test_proposal_commits_one_pending_action_and_one_revision(self):
        def proposal(_system, _message, max_tokens):
            self.model_calls.append(max_tokens)
            return ('{"kind":"propose_connector","proposal":'
                    '{"connector_id":"issues","display_name":"Issues","setup_kind":"api_key",'
                    '"purpose":"Review issues."}}')
        self.runtime.llm.call = proposal
        response, status = self.post(self.valid())
        self.assertEqual(status, 200)
        self.assertEqual(response["revision"], 1)
        self.assertEqual(response["action"], {"kind": "propose_connector", "state": "setup_required",
                                              "connector_id": "issues", "setup_kind": "api_key"})
        self.assertEqual(response["speech"], "I prepared a setup card for Issues.")
        self.assertEqual(self.store.workspace["revision"], 1)
        self.assertEqual(len(self.store.workspace["pending_actions"]), 1)

    def test_forbidden_provider_action_speech_fails_closed_without_api_or_store_leakage(self):
        def forbidden_proposal(_system, _message, max_tokens):
            self.model_calls.append(max_tokens)
            return ('{"kind":"propose_connector","speech":"Provider sentinel prose.","proposal":'
                    '{"connector_id":"issues","display_name":"Issues","setup_kind":"api_key",'
                    '"purpose":"Review issues."}}')
        self.runtime.llm.call = forbidden_proposal
        response, status = self.post(self.valid())
        self.assertEqual((response, status), ({"ok": False,
                                                "error": "Cordia Agent could not complete that request."}, 502))
        self.assertNotIn("Provider sentinel prose.", json.dumps(response))
        self.assertNotIn("Provider sentinel prose.", json.dumps(list(self.store.runs.values())))
        self.assertEqual(self.store.write_calls, [])
        self.assertEqual(self.store.workspace, workspace_state.empty("workspace_1"))

    def test_model_failure_does_not_write_a_run_or_workspace(self):
        def unavailable(*_args, **_kwargs):
            raise RuntimeError("provider private failure")
        self.runtime.llm.call = unavailable
        response, status = self.post(self.valid())
        self.assertEqual((response, status), ({"ok": False,
                                                "error": "Cordia Agent could not complete that request."}, 502))
        self.assertEqual(self.store.write_calls, [])
        self.assertEqual(self.store.workspace["revision"], 0)

    def test_human_mutation_returns_the_actual_saved_canonical_workspace(self):
        response, status = self.post({
            "id": "workspace_1", "mutation": {
                "kind": "add_window", "window": {"id": "notes", "title": "Notes"},
            },
        }, path="/surveyor/workspace/mutate")
        self.assertEqual(status, 200)
        self.assertEqual(response["workspace"], self.store.workspace)
        self.assertEqual(response["workspace"]["revision"], 1)

    def test_interface_projection_recomputes_after_an_intervening_agent_revision(self):
        stale = workspace_state.empty("workspace_1")
        self.store.workspace, _ = cordia_agent.apply_proposal(stale, {
            "kind": "propose_connector", "proposal": {
                "connector_id": "issues", "display_name": "Issues",
                "setup_kind": "api_key", "purpose": "Review issues.",
            },
        })
        self.store.workspace_read = stale
        response, status = self.post({
            "id": "workspace_1", "name": "Fresh interface", "description": "Fresh description",
            "definition": {},
        }, path="/surveyor/interface")
        self.assertEqual((response, status), ({"ok": True, "id": "workspace_1"}, 200))
        self.assertEqual((self.store.workspace["revision"],
                          len(self.store.workspace["pending_actions"]),
                          self.store.workspace["title"]), (2, 1, "Fresh interface"))

    def test_connector_refresh_recomputes_after_an_intervening_agent_revision(self):
        stale = workspace_state.empty("workspace_1")
        self.store.workspace, _ = cordia_agent.apply_proposal(stale, {
            "kind": "propose_connector", "proposal": {
                "connector_id": "issues", "display_name": "Issues",
                "setup_kind": "api_key", "purpose": "Review issues.",
            },
        })
        self.store.workspace_listing = [("workspace_1", stale)]
        response, status = self.post({"connector_states": {"github": "confirmed"}},
                                     path="/surveyor/connectors")
        self.assertEqual(status, 200)
        self.assertTrue(response["ok"])
        self.assertEqual((self.store.workspace["revision"],
                          len(self.store.workspace["pending_actions"]),
                          self.store.workspace["connectors"]),
                         (2, 1, [{"id": "github", "status": "confirmed",
                                 "implementation_status": "live",
                                 "lifecycle": "needs_handoff"}]))

    def test_server_derived_conflict_never_returns_success(self):
        self.store.interface_transaction_status = "conflict"
        self.store.connector_transaction_status = "conflict"
        interface, interface_status = self.post({
            "id": "workspace_1", "name": "Fresh interface", "description": "Fresh description",
            "definition": {},
        }, path="/surveyor/interface")
        connector, connector_status = self.post({"connector_states": {"github": "confirmed"}},
                                                 path="/surveyor/connectors")
        self.assertEqual((interface["ok"], interface_status), (False, 409))
        self.assertEqual((connector["ok"], connector_status), (False, 409))

    def test_atomic_derived_transaction_failure_returns_no_success_or_partial_state(self):
        before = deepcopy((self.store.workspace, self.store.connector_states, self.store.interfaces))
        self.store.interface_transaction_status = "failed"
        self.store.connector_transaction_status = "failed"
        interface, interface_status = self.post({
            "id": "workspace_1", "name": "Fresh interface", "description": "Fresh description",
            "definition": {},
        }, path="/surveyor/interface")
        connector, connector_status = self.post({"connector_states": {"github": "confirmed"}},
                                                 path="/surveyor/connectors")
        self.assertEqual((interface["ok"], interface_status), (False, 409))
        self.assertEqual((connector["ok"], connector_status), (False, 409))
        self.assertEqual((self.store.workspace, self.store.connector_states, self.store.interfaces), before)


if __name__ == "__main__":
    unittest.main()
