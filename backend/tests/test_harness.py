#!/usr/bin/env python3
"""Proves the test runner itself.

Run from backend/:
    python3 -m unittest            # discovery — must find and run this suite
    python3 -m unittest tests.test_harness -v

Stdlib unittest only, no DB, no network — every later suite in this tree is
held to the same bar, because the automated verify gate has to run on any
machine that can check out the repo.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestHarness(unittest.TestCase):
    def test_runner_runs(self):
        """The trivial passing test the build loop's Step 0 requires."""
        self.assertTrue(True)

    def test_sibling_backend_modules_are_importable(self):
        """The sys.path bootstrap above is what every suite here relies on to
        import backend modules; if it breaks, failures would blame the wrong
        thing. Note this import executes surveyor/__init__.py, which eagerly
        imports the fourteen submodules it declares — so those, but only
        those, are proven stdlib-only at import time here (psycopg2 is
        function-scoped in store.py). Modules outside that list (library,
        langgraph_adapter, hitl_policy, ...) are only covered when a suite
        imports them directly, as test_library does."""
        from surveyor import types
        self.assertTrue(callable(types.assert_positive))


if __name__ == "__main__":
    unittest.main()
