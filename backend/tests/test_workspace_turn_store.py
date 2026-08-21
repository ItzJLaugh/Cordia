import os
import sys
import unittest
from copy import deepcopy
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import store, workspace_state


class TurnCursor:
    def __init__(self, database):
        self.database = database
        self.sql = ""
        self.params = ()
        self.rowcount = 0

    def __enter__(self): return self
    def __exit__(self, *_args): return False

    def execute(self, sql, params=None):
        self.sql = " ".join(sql.split())
        self.params = params or ()
        self.rowcount = 0
        if self.sql.startswith("UPDATE surveyor_workspaces"):
            state, workspace_id, email = self.params
            if (email, workspace_id) in self.database.workspaces:
                self.database.workspaces[(email, workspace_id)] = deepcopy(state)
                self.rowcount = 1
        elif self.sql.startswith("INSERT INTO surveyor_workspaces"):
            workspace_id, email, state = self.params
            self.database.workspaces.setdefault((email, workspace_id), deepcopy(state))
            self.rowcount = 1
        elif self.sql.startswith("INSERT INTO surveyor_runs"):
            workspace_id, email, user, speech, meta, key, kind = self.params
            self.database.runs.append({"workspace_id": workspace_id, "email": email,
                                       "input": user, "output": speech, "meta": deepcopy(meta),
                                       "key": key, "kind": kind})

    def fetchone(self):
        if "SELECT state FROM surveyor_workspaces" in self.sql:
            workspace_id, email = self.params
            state = self.database.workspaces.get((email, workspace_id))
            return (deepcopy(state),) if state is not None else None
        if "SELECT meta FROM surveyor_runs" in self.sql:
            email, workspace_id, key, kind = self.params
            row = next((run for run in self.database.runs if run["email"] == email
                        and run["workspace_id"] == workspace_id and run["key"] == key
                        and run["kind"] == kind), None)
            return (deepcopy(row["meta"]),) if row else None
        if "SELECT 1 FROM surveyor_runs" in self.sql:
            email, workspace_id, kind = self.params
            return (1,) if any(run["email"] == email and run["workspace_id"] == workspace_id
                                and run["kind"] == kind and run["key"] for run in self.database.runs) else None
        return None

    def fetchall(self):
        if "SELECT input,output FROM surveyor_runs" not in self.sql:
            return []
        email, workspace_id, kind, limit = self.params
        rows = [run for run in self.database.runs if run["email"] == email
                and run["workspace_id"] == workspace_id and run["kind"] == kind and run["key"]]
        return [(run["input"], run["output"]) for run in rows[-limit:]]


class TurnConnection:
    def __init__(self, database): self.database = database
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def cursor(self): return TurnCursor(self.database)


class TurnDatabase:
    def __init__(self):
        self.workspaces = {("owner@example.test", "workspace_1"): workspace_state.empty("workspace_1")}
        self.runs = [{
            "workspace_id": "workspace_1", "email": "owner@example.test", "input": "legacy input",
            "output": "legacy provider output", "meta": {"llm": "legacy"}, "key": None, "kind": None,
        }]


class TestWorkspaceTurnStore(unittest.TestCase):
    def setUp(self):
        self.database = TurnDatabase()
        self.connection = TurnConnection(self.database)
        self.patches = [patch.object(store, "_conn", return_value=self.connection),
                        patch.object(store, "_J", side_effect=lambda value: deepcopy(value))]
        for item in self.patches: item.start()

    def tearDown(self):
        for item in reversed(self.patches): item.stop()

    def public(self, revision=0):
        return {"ok": True, "speech": "Safe speech.", "action": None, "revision": revision}

    def test_legacy_runs_never_become_workspace_turn_history_or_greeting_truth(self):
        self.assertEqual(store.recent_workspace_turns("owner@example.test", "workspace_1"), [])
        self.assertFalse(store.has_workspace_turns("owner@example.test", "workspace_1"))

    def test_owner_and_workspace_scoped_idempotency_and_history_use_production_store_functions(self):
        state = workspace_state.empty("workspace_1")
        committed = store.commit_workspace_turn("owner@example.test", "workspace_1", 0, "turn_1",
                                                "Safe request.", self.public(), state)
        self.assertEqual(committed["status"], "committed")
        self.assertEqual(store.get_run_by_idempotency("owner@example.test", "workspace_1", "turn_1"),
                         self.public())
        self.assertEqual(store.recent_workspace_turns("owner@example.test", "workspace_1"), [{
            "user": "Safe request.", "assistant": "Safe speech.",
        }])
        self.assertTrue(store.has_workspace_turns("owner@example.test", "workspace_1"))
        self.assertIsNone(store.get_run_by_idempotency("other@example.test", "workspace_1", "turn_1"))
        self.assertEqual(store.recent_workspace_turns("other@example.test", "workspace_1"), [])
        self.assertEqual(store.commit_workspace_turn("other@example.test", "workspace_1", 0, "turn_2",
                                                      "No access.", self.public(), state)["status"], "missing")

    def test_duplicate_key_replays_once_and_every_canonical_save_advances_the_revision(self):
        state = workspace_state.empty("workspace_1")
        self.assertEqual(store.commit_workspace_turn("owner@example.test", "workspace_1", 0, "turn_1",
                                                     "Safe request.", self.public(), state)["status"], "committed")
        self.assertEqual(store.commit_workspace_turn("owner@example.test", "workspace_1", 0, "turn_1",
                                                     "Changed request.", self.public(), state)["status"], "prior")
        changed = deepcopy(self.database.workspaces[("owner@example.test", "workspace_1")])
        changed["title"] = "Human update"
        store.save_workspace("owner@example.test", "workspace_1", changed)
        self.assertEqual(self.database.workspaces[("owner@example.test", "workspace_1")]["revision"], 1)
        changed = deepcopy(self.database.workspaces[("owner@example.test", "workspace_1")])
        changed["connectors"] = [{"id": "github", "status": "confirmed"}]
        store.save_workspace("owner@example.test", "workspace_1", changed)
        self.assertEqual(self.database.workspaces[("owner@example.test", "workspace_1")]["revision"], 2)
        changed = deepcopy(self.database.workspaces[("owner@example.test", "workspace_1")])
        changed["connectors"][0]["runtime_status"] = "live"
        store.save_workspace("owner@example.test", "workspace_1", changed)
        self.assertEqual(self.database.workspaces[("owner@example.test", "workspace_1")]["revision"], 3)
        changed = deepcopy(self.database.workspaces[("owner@example.test", "workspace_1")])
        changed["description"] = "Interface update"
        store.save_workspace("owner@example.test", "workspace_1", changed)
        self.assertEqual(self.database.workspaces[("owner@example.test", "workspace_1")]["revision"], 4)
        self.assertEqual(store.commit_workspace_turn("owner@example.test", "workspace_1", 0, "turn_2",
                                                     "Stale write.", self.public(), state)["status"], "conflict")

    def test_invalid_stored_revision_fails_closed_but_missing_legacy_revision_is_zero(self):
        state = workspace_state.empty("workspace_1")
        self.database.workspaces[("owner@example.test", "workspace_1")] = {"id": "workspace_1"}
        self.assertEqual(store.commit_workspace_turn("owner@example.test", "workspace_1", 0, "turn_1",
                                                     "Legacy state.", self.public(), state)["status"], "committed")
        self.database.workspaces[("owner@example.test", "workspace_1")]["revision"] = "forged"
        self.assertEqual(store.commit_workspace_turn("owner@example.test", "workspace_1", 0, "turn_2",
                                                     "Corrupt state.", self.public(), state)["status"], "conflict")


if __name__ == "__main__":
    unittest.main()
