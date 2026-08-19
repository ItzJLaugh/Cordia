import importlib
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import surveyor
from surveyor import freeform, scenarios, store, types


def completed_profile():
    profile = types.empty_profile()
    profile["signals"] = {
        key: (
            f"answer-{key}"
            if types.SIGNAL_SCHEMA[key] is None
            else next(value for value in types.SIGNAL_SCHEMA[key] if value != "unknown")
        )
        for key in types.SIGNAL_PRIORITY[:6]
    }
    profile["scenarios"] = {
        item["id"]: item["options"][0][0] for item in scenarios.SCENARIOS[:3]
    }
    profile["freeform"] = {key: "known answer" for key in freeform.KEYS}
    profile["private"] = {
        "token": "github_pat_PRIVATE",
        "path": r"C:\private\workspace",
    }
    return profile


class FakeCursor:
    def __init__(self, existing=None, fail_on=None):
        self.existing = existing
        self.fail_on = fail_on
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        compact = " ".join(str(sql).split())
        self.calls.append((compact, params))
        if self.fail_on and self.fail_on in compact:
            raise RuntimeError("forced transaction failure")

    def fetchone(self):
        return (self.existing,) if self.existing else None


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.outcome = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_args):
        self.outcome = "rollback" if exc_type else "commit"
        return False

    def cursor(self):
        return self._cursor


class TestWorkspacePreparation(unittest.TestCase):
    def test_prepares_fixed_definition_canonical_state_and_compiled_artifacts(self):
        prepared = surveyor.workspace_generation.prepare(
            "workspace-1", completed_profile(), {"github": "suggested"}
        )

        self.assertEqual(prepared["name"], "My Workspace")
        self.assertEqual(
            prepared["description"],
            "A Cordia workspace shaped from your Surveyor profile.",
        )
        self.assertEqual(prepared["workspace"]["id"], "workspace-1")
        self.assertEqual(
            prepared["workspace"]["context_sources"],
            [{"kind": "artifact", "ref": "runtime/fde-tasks.md"}],
        )
        self.assertIn("source/operator.md", prepared["artifacts"])
        self.assertIn("runtime/fde-tasks.md", prepared["artifacts"])
        self.assertNotIn("reason", prepared["definition"])
        self.assertNotIn("github_pat_PRIVATE", repr(prepared))
        self.assertNotIn(r"C:\private\workspace", repr(prepared))


class TestAtomicInitialWorkspaceStore(unittest.TestCase):
    def prepared(self):
        return surveyor.workspace_generation.prepare(
            "workspace-1", completed_profile(), {}
        )

    def run_store(self, cursor):
        connection = FakeConnection(cursor)
        with patch.object(store, "_conn", return_value=connection), patch.object(
            store, "_J", side_effect=lambda value: value
        ):
            result = store.ensure_initial_workspace(
                "owner@example.test", self.prepared()
            )
        return result, connection

    def test_locks_owner_then_inserts_interface_workspace_and_artifacts(self):
        cursor = FakeCursor()

        result, connection = self.run_store(cursor)

        self.assertEqual(result, ("workspace-1", True))
        self.assertEqual(connection.outcome, "commit")
        self.assertEqual(len(cursor.calls), 5)
        self.assertIn("pg_advisory_xact_lock", cursor.calls[0][0])
        self.assertIn("WHERE email=%s AND archived=FALSE", cursor.calls[1][0])
        self.assertEqual(cursor.calls[1][1], ("owner@example.test",))
        self.assertIn("INSERT INTO surveyor_interfaces", cursor.calls[2][0])
        self.assertIn("INSERT INTO surveyor_workspaces", cursor.calls[3][0])
        self.assertIn("INSERT INTO surveyor_artifacts", cursor.calls[4][0])

    def test_returns_existing_owner_workspace_without_writes(self):
        cursor = FakeCursor(existing="existing-workspace")

        result, connection = self.run_store(cursor)

        self.assertEqual(result, ("existing-workspace", False))
        self.assertEqual(connection.outcome, "commit")
        self.assertEqual(len(cursor.calls), 2)

    def test_transaction_failure_propagates_for_connection_rollback(self):
        cursor = FakeCursor(fail_on="INSERT INTO surveyor_workspaces")
        connection = FakeConnection(cursor)

        with patch.object(store, "_conn", return_value=connection), patch.object(
            store, "_J", side_effect=lambda value: value
        ):
            with self.assertRaisesRegex(RuntimeError, "forced transaction failure"):
                store.ensure_initial_workspace(
                    "owner@example.test", self.prepared()
                )

        self.assertEqual(connection.outcome, "rollback")


class TestWorkspaceGenerationRoute(unittest.TestCase):
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

    def handler(self, body, email="owner@example.test"):
        handler = object.__new__(self.backend.H)
        handler.path = "/surveyor/workspace/generate"
        handler._body = lambda: body
        handler._surv_guard = lambda: (email, None) if email else (None, True)
        handler._json = lambda payload, status=200: setattr(
            handler, "response", (payload, status)
        )
        handler.response = None
        return handler

    def runtime(self, complete=True, existing=False):
        calls = []
        profile = completed_profile() if complete else types.empty_profile()

        def prepare(candidate, received_profile, connector_states):
            calls.append(("prepare", candidate, received_profile, connector_states))
            return {"id": candidate, "safe": True}

        runtime = SimpleNamespace(
            pipeline=SimpleNamespace(
                load_profile=lambda email: calls.append(("profile", email)) or profile
            ),
            types=SimpleNamespace(onboarding_complete=lambda value: complete and value is profile),
            workspace_generation=SimpleNamespace(prepare=prepare),
            store=SimpleNamespace(
                get_connector_states=lambda email: calls.append(("connectors", email)) or {},
                ensure_initial_workspace=lambda email, prepared: calls.append(
                    ("ensure", email, prepared)
                )
                or ("workspace-1", not existing),
                log_event=lambda email, event, payload: calls.append(
                    ("event", email, event, payload)
                ),
            ),
        )
        return runtime, calls

    def test_completed_owner_receives_only_bounded_idempotent_result(self):
        runtime, calls = self.runtime(complete=True)
        handler = self.handler({})

        with patch.object(self.backend, "surveyor", runtime):
            handler.do_POST()

        self.assertEqual(
            handler.response,
            ({"ok": True, "id": "workspace-1", "created": True}, 200),
        )
        self.assertEqual(calls[0], ("profile", "owner@example.test"))
        self.assertEqual(calls[1], ("connectors", "owner@example.test"))
        self.assertEqual(calls[-1], (
            "event", "owner@example.test", "workspace_generated", {"id": "workspace-1"}
        ))
        public = repr(handler.response)
        self.assertNotIn("github_pat_PRIVATE", public)
        self.assertNotIn(r"C:\private\workspace", public)
        self.assertNotIn("artifacts", public)

    def test_repeated_generation_returns_created_false_without_second_event(self):
        runtime, calls = self.runtime(complete=True, existing=True)
        handler = self.handler({})

        with patch.object(self.backend, "surveyor", runtime):
            handler.do_POST()

        self.assertEqual(
            handler.response,
            ({"ok": True, "id": "workspace-1", "created": False}, 200),
        )
        self.assertFalse(any(call[0] == "event" for call in calls))

    def test_incomplete_or_nonempty_requests_stop_before_persistence(self):
        for body, expected_status in [({}, 409), ({"name": "forged"}, 400)]:
            runtime, calls = self.runtime(complete=False)
            handler = self.handler(body)
            with patch.object(self.backend, "surveyor", runtime):
                handler.do_POST()
            self.assertEqual(handler.response[1], expected_status)
            self.assertFalse(any(call[0] in {"connectors", "prepare", "ensure"} for call in calls))

    def test_unauthenticated_request_stops_before_profile_read(self):
        runtime, calls = self.runtime()
        handler = self.handler({}, email=None)

        with patch.object(self.backend, "surveyor", runtime):
            handler.do_POST()

        self.assertIsNone(handler.response)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
