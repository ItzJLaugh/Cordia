import copy
import importlib
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_MISSING = object()
_ORIGINAL_CORDIA_AUTH = sys.modules.get("cordia_auth", _MISSING)
from surveyor import alidora


class TestAlidora(unittest.TestCase):
    def test_map_payload_is_safe_and_deterministic(self):
        state = {
            "id": "w-1",
            "title": "Launch",
            "agents": [{"id": "review", "name": "Review"}],
            "skills": [],
            "connectors": [],
            "permissions": {"mode": "compiled"},
            "context_sources": [{"id": "C:\\private\\repo"}],
            "provenance": [{"secret": "must-not-leak"}],
        }

        result = alidora.map_payload(state)

        self.assertEqual(
            result["workspace"],
            {"id": "w-1", "title": "Launch", "description": ""},
        )
        self.assertEqual(
            result["nodes"],
            [{"id": "agent:review", "kind": "agent", "label": "Review", "detail": ""}],
        )
        self.assertEqual(
            result["summary"],
            {"agents": 1, "skills": 0, "connectors": 0, "approval_mode": "compiled"},
        )
        self.assertNotIn("private", repr(result))
        self.assertNotIn("must-not-leak", repr(result))

    def test_map_payload_discards_unresolved_references(self):
        result = alidora.map_payload({"id": "w", "workflow": {"steps": [{"agent_id": "missing"}]}})

        self.assertEqual(result["nodes"], [])
        self.assertEqual(result["edges"], [])

    def test_map_payload_does_not_mutate_its_input_state(self):
        state = {
            "id": "w-1",
            "agents": [{"id": "review", "name": "Review"}],
            "skills": [{"id": "draft", "name": "Draft"}],
            "workflow": {"steps": [{"agentId": "review", "toolIds": ["draft"]}]},
        }
        before = copy.deepcopy(state)

        alidora.map_payload(state)

        self.assertEqual(state, before)

    def test_map_payload_projects_canonical_workflow_edges_only(self):
        result = alidora.map_payload(
            {
                "agents": [
                    {"id": "writer", "name": "Writer"},
                    {"id": "review", "name": "Review"},
                    {"name": "Malformed"},
                ],
                "skills": [
                    {"id": "draft", "name": "Draft"},
                    {"id": "check", "name": "Check"},
                ],
                "connectors": [{"id": "github", "name": "GitHub"}],
                "workflow": {
                    "steps": [
                        {"id": "write", "agentId": "writer", "toolIds": ["draft", None, "missing"]},
                        {"id": "review", "agentId": "review", "toolIds": ["check", "missing"]},
                        {"agentId": "missing", "toolIds": ["draft"]},
                    ]
                },
            }
        )

        self.assertEqual(
            [node["id"] for node in result["nodes"]],
            ["agent:review", "agent:writer", "connector:github", "skill:check", "skill:draft"],
        )
        self.assertEqual(
            result["edges"],
            [
                {"from": "agent:review", "to": "skill:check"},
                {"from": "agent:writer", "to": "agent:review"},
                {"from": "agent:writer", "to": "skill:draft"},
            ],
        )

    def test_map_payload_drops_unsafe_strings_from_every_emitted_position(self):
        result = alidora.map_payload(
            {
                "id": "C:\\private\\workspace",
                "title": "/private/project",
                "description": "token=must-not-leak",
                "agents": [
                    {"id": "C:\\private\\agent", "name": "password=hunter2"},
                    {"id": "safe-agent", "name": "Review", "description": "sk-secret-value"},
                ],
                "skills": [{"id": "safe-skill", "name": "Bearer private-token", "description": "Useful"}],
                "connectors": [{"id": "safe-connector", "name": "Connector", "description": "\\\\server\\share"}],
                "permissions": {"mode": "authorization=private"},
            }
        )

        self.assertEqual(result["workspace"], {"id": "", "title": "", "description": ""})
        self.assertEqual(
            result["nodes"],
            [
                {"id": "agent:safe-agent", "kind": "agent", "label": "Review", "detail": ""},
                {"id": "connector:safe-connector", "kind": "connector", "label": "Connector", "detail": ""},
                {"id": "skill:safe-skill", "kind": "skill", "label": "", "detail": "Useful"},
            ],
        )
        self.assertEqual(result["summary"]["approval_mode"], "")
        for forbidden in ("private", "must-not-leak", "hunter2", "secret-value", "Bearer", "server"):
            self.assertNotIn(forbidden, repr(result))

    def test_map_payload_rejects_duplicate_ids_independently_of_input_order(self):
        first = {
            "agents": [
                {"id": "same", "name": "First"},
                {"id": "same", "name": "Second"},
                {"id": "other", "name": "Other"},
            ]
        }
        second = {"agents": list(reversed(first["agents"]))}

        self.assertEqual(alidora.map_payload(first), alidora.map_payload(second))
        self.assertEqual(
            alidora.map_payload(first)["nodes"],
            [{"id": "agent:other", "kind": "agent", "label": "Other", "detail": ""}],
        )

    def test_map_payload_rejects_control_characters_and_overlong_identifiers(self):
        result = alidora.map_payload(
            {
                "id": "workspace\x00id",
                "title": "Normal\nTitle",
                "agents": [{"id": "a" * 81, "name": "Too long"}],
                "skills": [{"id": "valid", "name": "Useful\x1f detail"}],
            }
        )

        self.assertEqual(result["workspace"], {"id": "", "title": "", "description": ""})
        self.assertEqual(
            result["nodes"],
            [{"id": "skill:valid", "kind": "skill", "label": "", "detail": ""}],
        )

    def test_map_payload_drops_embedded_paths_and_common_credential_shapes(self):
        result = alidora.map_payload(
            {
                "id": "w1",
                "title": "Build from C:\\private\\repo",
                "description": "See /home/jacks/private/project for details",
                "agents": [
                    {"id": "review", "name": "Review Notes", "description": "Checks product evidence."},
                    {"id": "path", "name": "Open \\\\server\\share", "description": "xoxb-123456789012-abcdefghijk"},
                ],
                "skills": [{"id": "deploy", "name": "ghp_abcdefghijklmnopqrstuvwxyz", "description": "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"}],
                "connectors": [{"id": "database", "name": "Postgres", "description": "postgres://user:password@db.example/internal"}],
            }
        )

        self.assertEqual(result["workspace"], {"id": "w1", "title": "", "description": ""})
        self.assertEqual(
            result["nodes"],
            [
                {"id": "agent:path", "kind": "agent", "label": "", "detail": ""},
                {"id": "agent:review", "kind": "agent", "label": "Review Notes", "detail": "Checks product evidence."},
                {"id": "connector:database", "kind": "connector", "label": "Postgres", "detail": ""},
                {"id": "skill:deploy", "kind": "skill", "label": "", "detail": ""},
            ],
        )
        for forbidden in ("private", "home", "server", "xoxb", "ghp", "AKIA", "password@"):
            self.assertNotIn(forbidden, repr(result))

    def test_map_payload_drops_remaining_posix_and_key_shapes(self):
        posix_usr = "Run /usr/local/bin/tool"
        posix_root = "Read /root/private/key"
        aws_secret = "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        github_pat = "github_pat_abcdefghijklmnopqrstuvwxyz0123456789"
        result = alidora.map_payload(
            {
                "title": posix_usr,
                "description": posix_root,
                "agents": [{"id": "safe", "name": "Review Notes", "description": aws_secret}],
                "skills": [{"id": "safe-skill", "name": github_pat, "description": "Useful summary"}],
            }
        )

        self.assertEqual(result["workspace"], {"id": "", "title": "", "description": ""})
        self.assertEqual(
            result["nodes"],
            [
                {"id": "agent:safe", "kind": "agent", "label": "Review Notes", "detail": ""},
                {"id": "skill:safe-skill", "kind": "skill", "label": "", "detail": "Useful summary"},
            ],
        )
        for forbidden in (posix_usr, posix_root, aws_secret, github_pat):
            self.assertNotIn(forbidden, repr(result))


class TestAlidoraMapEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior_training_backend = sys.modules.get("training_backend", _MISSING)
        cls._auth_patch = patch.dict(sys.modules, {"cordia_auth": SimpleNamespace()})
        cls._auth_patch.start()
        sys.modules.pop("training_backend", None)
        cls._backend = importlib.import_module("training_backend")

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("training_backend", None)
        cls._auth_patch.stop()
        if cls._prior_training_backend is not _MISSING:
            sys.modules["training_backend"] = cls._prior_training_backend

    @property
    def backend(self):
        return type(self)._backend

    def handler(self, path="/surveyor/alidora/map?id=w-1", email="owner@example.test"):
        handler = object.__new__(self.backend.H)
        handler.path = path
        handler._surv_guard = lambda: (email, None) if email else (None, True)
        handler.response = None
        handler._json = lambda payload, status=200: setattr(handler, "response", (payload, status))
        return handler

    def test_requires_workspace_id_without_reading_state(self):
        handler = self.handler(path="/surveyor/alidora/map")

        def forbidden(*_args, **_kwargs):
            raise AssertionError("map endpoint must not read state without an id")

        surveyor = SimpleNamespace(store=SimpleNamespace(get_workspace=forbidden), alidora=alidora)
        with patch.object(self.backend, "surveyor", surveyor):
            handler._surv_alidora_map()

        self.assertEqual(handler.response, ({"ok": False, "error": "workspace id is required"}, 400))

    def test_hides_another_users_workspace(self):
        handler = self.handler(email="other@example.test")
        state = {"id": "w-1", "title": "Owner workspace"}
        store = SimpleNamespace(
            get_workspace=lambda email, workspace_id: state
            if (email, workspace_id) == ("owner@example.test", "w-1")
            else None
        )
        surveyor = SimpleNamespace(store=store, alidora=alidora)

        with patch.object(self.backend, "surveyor", surveyor):
            handler._surv_alidora_map()

        self.assertEqual(handler.response, ({"ok": False, "error": "workspace not found"}, 404))

    def test_get_dispatch_returns_a_safe_map_for_the_authenticated_owners_workspace(self):
        handler = self.handler()
        state = {
            "id": "w-1",
            "title": "Launch",
            "description": "Ready",
            "agents": [{"id": "review", "name": "Review"}],
            "skills": [{"id": "draft", "name": "Draft"}],
            "workflow": {"steps": [{"agentId": "review", "toolIds": ["draft"]}]},
            "permissions": {"mode": "compiled"},
            "provenance": [{"secret": "must-not-leak"}],
        }
        surveyor = SimpleNamespace(
            store=SimpleNamespace(get_workspace=lambda email, workspace_id: state),
            alidora=alidora,
        )

        with patch.object(self.backend, "surveyor", surveyor):
            handler.do_GET()

        self.assertEqual(
            handler.response,
            (
                {
                    "ok": True,
                    "map": {
                        "workspace": {"id": "w-1", "title": "Launch", "description": "Ready"},
                        "nodes": [
                            {"id": "agent:review", "kind": "agent", "label": "Review", "detail": ""},
                            {"id": "skill:draft", "kind": "skill", "label": "Draft", "detail": ""},
                        ],
                        "edges": [{"from": "agent:review", "to": "skill:draft"}],
                        "summary": {"agents": 1, "skills": 1, "connectors": 0, "approval_mode": "compiled"},
                    },
                },
                200,
            ),
        )
        self.assertNotIn("must-not-leak", repr(handler.response))

    def test_unauthenticated_get_stops_before_reading_workspace_state(self):
        handler = self.handler(email=None)

        handler.do_GET()

        self.assertIsNone(handler.response)

    def test_only_reads_state_and_projects_the_map_without_writing_or_executing(self):
        handler = self.handler()

        def forbidden(*_args, **_kwargs):
            raise AssertionError("map endpoint must not write, execute, or set up connectors")

        store = SimpleNamespace(
            get_workspace=lambda _email, _workspace_id: {"id": "w-1"},
            save_workspace=forbidden,
            log_event=forbidden,
            get_interface=forbidden,
            get_connector_states=forbidden,
        )
        surveyor = SimpleNamespace(
            store=store,
            alidora=alidora,
            vault=SimpleNamespace(get=forbidden),
            skills=SimpleNamespace(execute=forbidden),
            capability_gateway=SimpleNamespace(execute=forbidden),
            connectors=SimpleNamespace(setup=forbidden),
        )

        with patch.object(self.backend, "surveyor", surveyor):
            handler._surv_alidora_map()

        self.assertEqual(
            handler.response,
            (
                {
                    "ok": True,
                    "map": {
                        "workspace": {"id": "w-1", "title": "", "description": ""},
                        "nodes": [],
                        "edges": [],
                        "summary": {"agents": 0, "skills": 0, "connectors": 0, "approval_mode": ""},
                    },
                },
                200,
            ),
        )


class TestZAlidoraImportIsolation(unittest.TestCase):
    def test_restores_the_prior_cordia_auth_module_entry(self):
        self.assertIs(sys.modules.get("cordia_auth", _MISSING), _ORIGINAL_CORDIA_AUTH)


if __name__ == "__main__":
    unittest.main()
