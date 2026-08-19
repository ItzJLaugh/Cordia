import importlib
import json
import os
import sys
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import pipeline, scenarios, types, workspace_generation, workspace_state


class MemoryStore:
    def __init__(self):
        self.conversations = {}
        self.transcripts = {}
        self.profiles = {}
        self.connector_states = {}
        self.artifacts = {}
        self.interfaces = {}
        self.workspaces_by_owner = {}
        self.events_by_owner = {}
        self.workspace_id = None
        self.interface_id = None

    def open_conversation(self, email):
        conversation_id = self.conversations.setdefault(email, f"conversation-{len(self.conversations) + 1}")
        self.transcripts.setdefault(conversation_id, [])
        return conversation_id

    def messages(self, conversation_id, limit=200):
        return deepcopy(self.transcripts.get(conversation_id, [])[:limit])

    def add_message(self, conversation_id, role, content, meta=None):
        self.transcripts.setdefault(conversation_id, []).append({
            "role": role,
            "content": content,
            "meta": deepcopy(meta or {}),
        })

    def log_event(self, email, event, payload=None):
        self.events_by_owner.setdefault(email, []).append((event, deepcopy(payload or {})))

    def get_profile(self, email):
        return deepcopy(self.profiles.get(email))

    def save_profile(self, email, profile):
        self.profiles[email] = deepcopy(profile)

    def get_connector_states(self, email):
        return deepcopy(self.connector_states.get(email, {}))

    def ensure_initial_workspace(self, email, prepared):
        existing = self.interfaces.get(email, [])
        if existing:
            return existing[0]["id"], False
        workspace_id = prepared["id"]
        self.workspace_id = workspace_id
        self.interface_id = workspace_id
        self.interfaces[email] = [{
            "id": workspace_id,
            "name": prepared["name"],
            "description": prepared["description"],
            "definition": deepcopy(prepared["definition"]),
        }]
        self.workspaces_by_owner.setdefault(email, {})[workspace_id] = deepcopy(prepared["workspace"])
        self.artifacts[email] = deepcopy(prepared["artifacts"])
        return workspace_id, True

    def get_workspace(self, email, workspace_id):
        return deepcopy(self.workspaces_by_owner.get(email, {}).get(workspace_id))

    def get_interface(self, email, workspace_id):
        return next((deepcopy(item) for item in self.interfaces.get(email, [])
                     if item["id"] == workspace_id), None)

    def save_workspace(self, email, workspace_id, state):
        self.workspaces_by_owner.setdefault(email, {})[workspace_id] = deepcopy(state)

    def list_interfaces(self, email):
        return deepcopy(self.interfaces.get(email, []))


class TestBetaIntakeJourney(unittest.TestCase):
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
        self.memory = MemoryStore()
        self.owner = "owner@example.test"

    @staticmethod
    def call_llm(system, user, max_tokens=None):
        if "Return ONLY a JSON object" in system:
            question = str(user)
            if "kind of work" in question:
                signal, value = "domain", "product operations"
            elif "one thing right" in question:
                signal, value = "primary_goal", "ship reliable customer work"
            else:
                signal, value = "domain", "product operations"
            return json.dumps({
                "signals": {signal: value},
                "evidence": [{
                    "criterion": "intent_clarity",
                    "summary": "Stated a bounded work need.",
                    "confidence": "high",
                    "source": "surveyor_conversation",
                }],
            })
        return ""

    def route_handler(self, path, email, body=None):
        handler = object.__new__(self.backend.H)
        handler.path = path
        handler._body = lambda: deepcopy(body if body is not None else {})
        handler._surv_guard = lambda: (email, None)
        handler._json = lambda payload, status=200: setattr(
            handler, "response", (deepcopy(payload), status)
        )
        handler.response = None
        return handler

    def test_twelve_turns_generate_and_recover_one_owner_scoped_workspace(self):
        public_trace = []
        prompted_stages = []
        with patch.object(pipeline, "store", self.memory):
            current = pipeline.start(self.owner)
            conversation_id = current["conversation_id"]
            public_trace.append(current)

            for index in range(types.ONBOARDING_TURN_LIMIT):
                prompted_stages.append(current["stage"])
                options = current.get("options") or []
                choice = None
                answer = f"A safe answer for turn {index + 1}."
                if options:
                    chosen = options[0]
                    choice = {"signal": current["key"], "value": chosen["value"]}
                    answer = chosen["label"]
                current = pipeline.turn(
                    self.owner, answer, self.call_llm, choice=choice
                )
                public_trace.append(current)
                if index == 5:
                    transcript_size = len(
                        self.memory.transcripts[
                            self.memory.conversations[self.owner]
                        ]
                    )
                    resumed = pipeline.start(self.owner)
                    self.assertEqual(resumed["conversation_id"], conversation_id)
                    self.assertEqual(resumed["stage"], current["stage"])
                    self.assertEqual(resumed["key"], current["key"])
                    self.assertEqual(
                        len(
                            self.memory.transcripts[
                                self.memory.conversations[self.owner]
                            ]
                        ),
                        transcript_size,
                    )
                    current = resumed
                    public_trace.append(resumed)

            self.assertEqual(
                prompted_stages,
                ["preferences"] * 6 + ["scenarios"] * 3 + ["freeform"] * 3,
            )
            self.assertTrue(current["onboarding"]["complete"])
            self.assertEqual(current["onboarding"]["turns_used"], 12)
            transcript = self.memory.transcripts[self.memory.conversations[self.owner]]
            self.assertEqual(
                len([message for message in transcript if message["role"] == "user"]),
                12,
            )

            runtime = SimpleNamespace(
                pipeline=pipeline,
                types=types,
                workspace_generation=workspace_generation,
                workspace_state=workspace_state,
                store=self.memory,
            )
            generate = self.route_handler(
                "/surveyor/workspace/generate", self.owner, {}
            )
            with patch.object(self.backend, "surveyor", runtime):
                generate.do_POST()
            generated_response, generated_status = generate.response

            repeated = self.route_handler(
                "/surveyor/workspace/generate", self.owner, {}
            )
            with patch.object(self.backend, "surveyor", runtime):
                repeated.do_POST()
            repeated_response, repeated_status = repeated.response

            workspace = self.route_handler(
                f"/surveyor/workspace?id={self.memory.workspace_id}", self.owner
            )
            with patch.object(self.backend, "surveyor", runtime):
                workspace._surv_workspace()
            workspace_response, workspace_status = workspace.response

        self.assertEqual(generated_status, 200)
        self.assertEqual(repeated_status, 200)
        self.assertEqual(workspace_status, 200)
        self.assertEqual(generated_response, {
            "ok": True, "id": self.memory.workspace_id, "created": True,
        })
        self.assertEqual(repeated_response, {
            "ok": True, "id": self.memory.workspace_id, "created": False,
        })
        self.assertEqual(workspace_response["workspace"]["id"], self.memory.workspace_id)
        self.assertEqual(self.memory.interface_id, self.memory.workspace_id)
        self.assertIn("source/operator.md", self.memory.artifacts[self.owner])
        self.assertIn("runtime/fde-tasks.md", self.memory.artifacts[self.owner])
        self.assertNotIn("score", repr(public_trace).lower())
        self.assertNotIn("certification", repr(public_trace).lower())

        outsider = "other@example.test"
        outsider_runtime = SimpleNamespace(
            workspace_state=workspace_state,
            store=self.memory,
        )
        hidden = self.route_handler(
            f"/surveyor/workspace?id={self.memory.workspace_id}", outsider
        )
        with patch.object(self.backend, "surveyor", outsider_runtime):
            hidden._surv_workspace()
        self.assertEqual(hidden.response, (
            {"ok": False, "error": "workspace not found"}, 404,
        ))
        self.assertEqual(self.memory.list_interfaces(outsider), [])


if __name__ == "__main__":
    unittest.main()
