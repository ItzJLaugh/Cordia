import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import profile_calibration, store, types, workspace_generation
from test_profile_calibration import VALID


class FakeCursor:
    def __init__(self, row=None):
        self.row = row
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self._cursor


class TestProfileMemory(unittest.TestCase):
    def test_compile_memory_is_bounded_inspectable_and_behavioral(self):
        memory = profile_calibration.compile_memory(VALID)

        self.assertIn("# Workspace Memory", memory)
        self.assertIn("Explain reasoning before conclusions.", memory)
        self.assertIn("Technology and software: advanced familiarity.", memory)
        self.assertIn("Survey version: research-2026-08", memory)
        self.assertNotIn("profile_018f0f4d", memory)
        self.assertNotIn("Show me how the dependencies fit together.", memory)
        self.assertLessEqual(len(memory), 5000)

    def test_compile_memory_never_changes_permission_or_fact_truth(self):
        memory = profile_calibration.compile_memory(VALID)
        for forbidden in ("ALLOW", "connected", "approved", "live connector"):
            self.assertNotIn(forbidden, memory)

    def test_workspace_memory_is_compiled_from_calibration_without_replacing_legacy_artifacts(self):
        profile = types.empty_profile()

        prepared = workspace_generation.prepare(
            "workspace-1", profile, calibration=VALID
        )

        self.assertEqual(
            prepared["description"],
            "A Cordia workspace shaped from your profile calibration.",
        )
        self.assertEqual(
            prepared["artifacts"]["source/memory.md"],
            profile_calibration.compile_memory(VALID),
        )
        self.assertIn("source/operator.md", prepared["artifacts"])
        self.assertIn("runtime/fde-tasks.md", prepared["artifacts"])

    def test_profile_calibration_store_is_owner_scoped_and_returns_a_copy(self):
        saved = FakeCursor()
        with patch.object(store, "_conn", return_value=FakeConnection(saved)), patch.object(
            store, "_J", side_effect=lambda value: value
        ):
            store.save_profile_calibration("owner@example.test", VALID)

        self.assertEqual(len(saved.calls), 1)
        self.assertIn("INSERT INTO surveyor_profiles(email, profile_calibration)", saved.calls[0][0])
        self.assertEqual(saved.calls[0][1], ("owner@example.test", VALID))

        loaded_value = profile_calibration.validate_result(VALID)
        loaded = FakeCursor((loaded_value,))
        with patch.object(store, "_conn", return_value=FakeConnection(loaded)):
            result = store.get_profile_calibration("owner@example.test")

        self.assertEqual(result, VALID)
        self.assertIsNot(result, loaded_value)
        self.assertIn("WHERE email=%s", loaded.calls[0][0])
        self.assertEqual(loaded.calls[0][1], ("owner@example.test",))


if __name__ == "__main__":
    unittest.main()
