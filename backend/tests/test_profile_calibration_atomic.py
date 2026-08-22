import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import store, workspace_state
from test_profile_calibration import VALID


def prepared():
    return {
        "id": "workspace-new",
        "name": "My Workspace",
        "description": "A Cordia workspace shaped from your profile calibration.",
        "definition": {"name": "My Workspace"},
        "workspace": {"id": "workspace-new"},
        "artifacts": {
            "source/operator.md": "new operator",
            "source/memory.md": "stale memory",
            "runtime/fde-tasks.md": "new runtime",
        },
    }


class AtomicCursor:
    def __init__(self, existing=None, artifacts=None, fail_on=None, connector_states=None,
                 owner_workspaces=None):
        self.existing = existing
        self.artifacts = artifacts
        self.fail_on = fail_on
        self.connector_states = connector_states
        self.owner_workspaces = owner_workspaces or []
        self.calls = []
        self._last_sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self._last_sql = " ".join(sql.split())
        self.calls.append((self._last_sql, params))
        if self.fail_on and self.fail_on in self._last_sql:
            raise RuntimeError("forced transaction failure")

    def fetchone(self):
        if "SELECT id FROM surveyor_interfaces" in self._last_sql:
            return (self.existing,) if self.existing else None
        if "SELECT source, runtime FROM surveyor_artifacts" in self._last_sql:
            return self.artifacts
        if "SELECT connector_states FROM surveyor_connector_preferences" in self._last_sql:
            return (self.connector_states,) if self.connector_states is not None else None
        return None

    def fetchall(self):
        if "SELECT id, state FROM surveyor_workspaces" in self._last_sql:
            return self.owner_workspaces
        return []


class AtomicConnection:
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


class TestAtomicProfileCalibrationCompletion(unittest.TestCase):
    def run_completion(self, cursor):
        connection = AtomicConnection(cursor)
        with patch.object(store, "_conn", return_value=connection), patch.object(
            store, "_J", side_effect=lambda value: value
        ):
            result = store.complete_profile_calibration(
                "owner@example.test", VALID, prepared(), "fresh memory"
            )
        return result, connection

    def test_existing_workspace_refresh_preserves_unrelated_source_and_runtime_artifacts(self):
        cursor = AtomicCursor(
            existing="workspace-existing",
            artifacts=({
                "source/operator.md": "keep operator",
                "source/user-notes.md": "keep notes",
                "source/memory.md": "old memory",
            }, {"runtime/fde-tasks.md": "keep runtime"}),
        )

        result, connection = self.run_completion(cursor)

        self.assertEqual(result, ("workspace-existing", False))
        self.assertEqual(connection.outcome, "commit")
        artifact_call = next(call for call in cursor.calls if "INSERT INTO surveyor_artifacts" in call[0])
        self.assertEqual(artifact_call[1][1], {
            "source/operator.md": "keep operator",
            "source/user-notes.md": "keep notes",
            "source/memory.md": "fresh memory",
        })
        self.assertEqual(artifact_call[1][2], {"runtime/fde-tasks.md": "keep runtime"})
        self.assertFalse(any("INSERT INTO surveyor_interfaces" in call[0] for call in cursor.calls))

    def test_failure_rolls_back_calibration_workspace_and_artifact_writes_together(self):
        cursor = AtomicCursor(fail_on="INSERT INTO surveyor_artifacts")
        connection = AtomicConnection(cursor)

        with patch.object(store, "_conn", return_value=connection), patch.object(
            store, "_J", side_effect=lambda value: value
        ):
            with self.assertRaisesRegex(RuntimeError, "forced transaction failure"):
                store.complete_profile_calibration(
                    "owner@example.test", VALID, prepared(), "fresh memory"
                )

        self.assertEqual(connection.outcome, "rollback")
        self.assertTrue(any("profile_calibration" in call[0] for call in cursor.calls))
        self.assertTrue(any("INSERT INTO surveyor_interfaces" in call[0] for call in cursor.calls))

    def test_calibration_creation_replaces_stale_candidate_runtime_with_locked_legacy_runtime(self):
        for current_status, stale_status in (("needs_attention", "live"),
                                             ("live", "needs_attention")):
            legacy = workspace_state.from_interface(
                "archived-legacy", {"name": "Archived"}, {"github": "confirmed"})
            legacy = workspace_state.record_connector_runtime(legacy, "github", current_status)
            cursor = AtomicCursor(
                connector_states={"github": "confirmed"},
                owner_workspaces=[("archived-legacy", legacy)],
            )
            candidate = prepared()
            candidate["definition"]["description"] = candidate["description"]
            candidate["workspace"] = workspace_state.from_interface(
                candidate["id"], candidate["definition"], {"github": "confirmed"})
            candidate["workspace"]["pending_actions"] = [{"id": "keep-calibration-action"}]
            candidate["workspace"] = workspace_state.record_connector_runtime(
                candidate["workspace"], "github", stale_status)
            connection = AtomicConnection(cursor)

            with patch.object(store, "_conn", return_value=connection), patch.object(
                store, "_J", side_effect=lambda value: value
            ):
                result = store.complete_profile_calibration(
                    "owner@example.test", VALID, candidate, "fresh memory"
                )

            self.assertEqual(result, ("workspace-new", True))
            self.assertEqual(connection.outcome, "commit")
            created = next(call[1][2] for call in cursor.calls
                           if "INSERT INTO surveyor_workspaces" in call[0])
            github = next(item for item in created["connectors"] if item["id"] == "github")
            self.assertEqual(github["runtime_status"], current_status)
            self.assertEqual(created["title"], "My Workspace")
            self.assertEqual(created["description"], candidate["description"])
            self.assertEqual(created["pending_actions"], [{"id": "keep-calibration-action"}])
            artifacts = next(call[1] for call in cursor.calls
                             if "INSERT INTO surveyor_artifacts" in call[0])
            self.assertEqual(artifacts[1]["source/operator.md"], "new operator")
            self.assertEqual(artifacts[1]["source/memory.md"], "fresh memory")


if __name__ == "__main__":
    unittest.main()
