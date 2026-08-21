import os
import sys
import unittest
from copy import deepcopy
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import store, workspace_state


class AtomicDatabase:
    def __init__(self):
        self.workspaces = {
            "workspace_1": {"email": "owner@example.test",
                            "state": workspace_state.empty("workspace_1")},
            "workspace_2": {"email": "owner@example.test",
                            "state": workspace_state.empty("workspace_2")},
        }
        self.interfaces = {
            "workspace_1": {"email": "owner@example.test", "name": "Old interface",
                            "description": "Old description", "definition": {}, "theme": {}},
        }
        self.connector_states = {}
        self.secrets = {}
        self.race = None
        self.workspace_updates = 0
        self.fail_after_workspace_updates = None
        self.lock_keys = []


class AtomicCursor:
    def __init__(self, database):
        self.database = database
        self.sql = ""
        self.params = ()
        self.rowcount = 0
        self.result = None
        self.results = []

    def __enter__(self): return self
    def __exit__(self, *_args): return False

    def execute(self, sql, params=None):
        self.sql = " ".join(sql.split())
        self.params = params or ()
        self.rowcount = 0
        self.result = None
        self.results = []
        if self.sql.startswith("SELECT pg_advisory_xact_lock"):
            self.database.lock_keys.append(self.params[0])
        elif self.sql.startswith("SELECT state FROM surveyor_workspaces"):
            workspace_id, email = self.params
            row = self.database.workspaces.get(workspace_id)
            self.result = (deepcopy(row["state"]),) if row and row["email"] == email else None
        elif self.sql.startswith("SELECT connector_states FROM surveyor_connector_preferences"):
            email = self.params[0]
            states = self.database.connector_states.get(email)
            self.result = (deepcopy(states),) if states is not None else None
        elif self.sql.startswith("SELECT id, state FROM surveyor_workspaces"):
            email = self.params[0]
            self.results = [(workspace_id, deepcopy(row["state"]))
                            for workspace_id, row in sorted(self.database.workspaces.items())
                            if row["email"] == email]
        elif self.sql.startswith("INSERT INTO surveyor_workspaces"):
            workspace_id, email, state = self.params
            if self.database.race and self.database.race[0] == workspace_id:
                _, rival_email, rival_state = self.database.race
                self.database.workspaces[workspace_id] = {
                    "email": rival_email, "state": deepcopy(rival_state)}
                self.database.race = None
            existing = self.database.workspaces.get(workspace_id)
            if existing and "DO UPDATE" in self.sql:
                if existing["email"] == email:
                    existing["state"] = deepcopy(state)
                    self.rowcount = 1
            elif not existing:
                self.database.workspaces[workspace_id] = {"email": email, "state": deepcopy(state)}
                self.rowcount = 1
                if "RETURNING" in self.sql:
                    self.result = (deepcopy(state),)
        elif self.sql.startswith("UPDATE surveyor_workspaces"):
            state, workspace_id, email = self.params
            self.database.workspace_updates += 1
            if (self.database.fail_after_workspace_updates is not None
                    and self.database.workspace_updates > self.database.fail_after_workspace_updates):
                raise RuntimeError("forced workspace transaction failure")
            row = self.database.workspaces.get(workspace_id)
            if row and row["email"] == email:
                row["state"] = deepcopy(state)
                self.rowcount = 1
        elif self.sql.startswith("INSERT INTO surveyor_interfaces"):
            iface_id, email, name, description, definition, theme = self.params
            existing = self.database.interfaces.get(iface_id)
            if existing and existing["email"] != email:
                return
            self.database.interfaces[iface_id] = {
                "email": email, "name": name, "description": description,
                "definition": deepcopy(definition), "theme": deepcopy(theme),
            }
            self.rowcount = 1
            if "RETURNING" in self.sql:
                self.result = (iface_id,)
        elif self.sql.startswith("INSERT INTO surveyor_connector_preferences"):
            email, states = self.params
            self.database.connector_states[email] = deepcopy(states)
            self.rowcount = 1
        elif self.sql.startswith("INSERT INTO surveyor_secrets"):
            secret_ref, email, connector, ciphertext = self.params
            self.database.secrets[secret_ref] = (email, connector, bytes(ciphertext))
            self.rowcount = 1

    def fetchone(self):
        return self.result

    def fetchall(self):
        return deepcopy(self.results)


class AtomicConnection:
    def __init__(self, database):
        self.database = database
        self.snapshot = None
        self.outcome = None

    def __enter__(self):
        self.snapshot = deepcopy(self.database.__dict__)
        return self

    def __exit__(self, exc_type, *_args):
        self.outcome = "rollback" if exc_type else "commit"
        if exc_type:
            self.database.__dict__.clear()
            self.database.__dict__.update(deepcopy(self.snapshot))
        return False

    def cursor(self):
        return AtomicCursor(self.database)


class TestWorkspaceTransactions(unittest.TestCase):
    def setUp(self):
        self.database = AtomicDatabase()
        self.connection = AtomicConnection(self.database)
        self.patches = [patch.object(store, "_conn", return_value=self.connection),
                        patch.object(store, "_J", side_effect=lambda value: deepcopy(value))]
        for item in self.patches: item.start()

    def tearDown(self):
        for item in reversed(self.patches): item.stop()

    def test_absent_workspace_create_never_overwrites_same_or_cross_owner_race(self):
        candidate = workspace_state.empty("created")
        candidate["pending_actions"] = [{"kind": "candidate"}]
        same_owner = workspace_state.empty("created")
        same_owner["revision"] = 4
        same_owner["pending_actions"] = [{"kind": "agent"}]
        self.database.race = ("created", "owner@example.test", same_owner)
        result = store.save_workspace("owner@example.test", "created", candidate, 0)
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(self.database.workspaces["created"]["state"], same_owner)

        candidate = workspace_state.empty("cross_owner")
        other_owner = workspace_state.empty("cross_owner")
        other_owner["revision"] = 7
        other_owner["pending_actions"] = [{"kind": "other"}]
        self.database.race = ("cross_owner", "other@example.test", other_owner)
        result = store.save_workspace("owner@example.test", "cross_owner", candidate, 0)
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(self.database.workspaces["cross_owner"], {
            "email": "other@example.test", "state": other_owner})

    def test_interface_projection_rolls_back_legacy_row_when_workspace_write_fails(self):
        self.database.fail_after_workspace_updates = 0
        before = deepcopy(self.database.__dict__)
        result = store.save_interface_projection(
            "owner@example.test", "workspace_1", "Fresh interface", "Fresh description", {}, {})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.database.__dict__, before)
        self.assertEqual(self.connection.outcome, "rollback")

    def test_connector_projection_rolls_back_preferences_secret_and_prior_workspace_updates(self):
        self.database.fail_after_workspace_updates = 1
        before = deepcopy(self.database.__dict__)
        result = store.save_connector_projection(
            "owner@example.test", {"github": "confirmed"},
            secret=("secret_1", "github", b"ciphertext"), runtime_status="live")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.database.__dict__, before)
        self.assertEqual(self.connection.outcome, "rollback")

    def test_runtime_projection_rolls_back_all_workspaces_after_later_failure(self):
        self.database.fail_after_workspace_updates = 1
        before = deepcopy(self.database.__dict__)
        result = store.save_connector_runtime_projection("owner@example.test", "github", "live")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.database.__dict__, before)
        self.assertEqual(self.connection.outcome, "rollback")

    def test_connector_projection_merges_from_the_locked_preference_state(self):
        self.database.connector_states["owner@example.test"] = {"linear": "confirmed"}
        result = store.save_connector_projection(
            "owner@example.test", {"github": "confirmed"})
        self.assertEqual(result, {
            "status": "committed",
            "connector_states": {"linear": "confirmed", "github": "confirmed"},
            "workspace_ids": ["workspace_1", "workspace_2"],
        })
        self.assertEqual(self.database.connector_states["owner@example.test"], {
            "linear": "confirmed", "github": "confirmed"})

    def test_bulk_projection_and_absent_creator_share_one_owner_workspace_set_lock(self):
        store.save_connector_runtime_projection("owner@example.test", "github", "live")
        candidate = workspace_state.empty("created_after_bulk")
        self.assertEqual(store.save_workspace(
            "owner@example.test", "created_after_bulk", candidate, 0)["status"], "saved")
        set_locks = [key for key in self.database.lock_keys if "workspace-set" in key]
        self.assertGreaterEqual(len(set_locks), 2)
        self.assertEqual(set(set_locks), {"surveyor-workspace-set:owner@example.test"})

    def test_absent_creator_refreshes_a_stale_connector_projection_after_its_set_lock(self):
        candidate = workspace_state.empty("created_after_connector_bulk")
        candidate["title"] = "Keep this local work"
        candidate["connectors"] = [{"id": "github", "status": "suggested"}]
        self.assertEqual(store.save_connector_projection(
            "owner@example.test", {"github": "confirmed"}, runtime_status="live")["status"],
            "committed")
        result = store.save_workspace(
            "owner@example.test", "created_after_connector_bulk", candidate, 0)
        self.assertEqual(result["status"], "saved")
        self.assertEqual(result["workspace"]["title"], "Keep this local work")
        github = next(item for item in result["workspace"]["connectors"]
                      if item["id"] == "github")
        self.assertEqual(github["status"], "confirmed")
        self.assertEqual(github["runtime_status"], "live")

    def test_legacy_materialization_reads_connector_truth_after_the_workspace_set_lock(self):
        """A legacy candidate cannot retain the connector snapshot from before a bulk write."""
        self.assertEqual(store.save_connector_projection(
            "owner@example.test", {"github": "confirmed"}, runtime_status="live")["status"],
            "committed")
        lock_count = len(self.database.lock_keys)
        result = store.materialize_interface_workspace(
            "owner@example.test", "legacy_after_bulk", {"name": "Legacy"})
        self.assertEqual(result["status"], "committed")
        github = next(item for item in result["workspace"]["connectors"]
                      if item["id"] == "github")
        self.assertEqual(github["status"], "confirmed")
        self.assertEqual(github["runtime_status"], "live")
        locks = self.database.lock_keys[lock_count:]
        self.assertEqual(locks[:2], ["surveyor-workspace-set:owner@example.test",
                         "surveyor-connector-preferences:owner@example.test"])

    def test_new_interface_materialization_inherits_current_connector_runtime(self):
        self.assertEqual(store.save_connector_projection(
            "owner@example.test", {"github": "confirmed"}, runtime_status="live")["status"],
            "committed")
        result = store.save_interface_projection(
            "owner@example.test", "interface_after_bulk", "Fresh", "", {}, {})
        self.assertEqual(result["status"], "committed")
        github = next(item for item in result["workspace"]["connectors"]
                      if item["id"] == "github")
        self.assertEqual((github["status"], github["runtime_status"]), ("confirmed", "live"))


if __name__ == "__main__":
    unittest.main()
