import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("production_review.py")


def load_review_module():
    spec = importlib.util.spec_from_file_location("production_review", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("production review module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CheckSpecsTests(unittest.TestCase):
    def test_check_specs_use_the_fixed_allow_list(self):
        review = load_review_module()

        self.assertEqual(
            [x.check_id for x in review.check_specs(platform="linux", python="python3")],
            [
                "backend-tests",
                "dashboard-install",
                "dashboard-tests",
                "dashboard-build",
                "desktop-install",
                "desktop-tests",
                "dashboard-release",
                "commit-diff-check",
            ],
        )
        self.assertEqual(
            review.check_specs(platform="linux", python="python3")[0].argv,
            ("python3", "-m", "unittest", "discover", "-s", "tests", "-v"),
        )
        self.assertEqual(
            review.check_specs(platform="linux", python="python3")[-1].argv,
            ("git", "diff", "--check", "HEAD^", "HEAD"),
        )


class RunReviewTests(unittest.TestCase):
    EXPECTED_SHA = "a" * 40

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        self.review = load_review_module()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_run_review_records_bounded_results_for_the_fixed_checks(self):
        calls = []

        def executor(argv, **kwargs):
            calls.append((argv, kwargs))
            if tuple(argv) == ("git", "rev-parse", "HEAD"):
                return subprocess.CompletedProcess(argv, 0, stdout=self.EXPECTED_SHA + "\n", stderr="")
            return subprocess.CompletedProcess(
                argv, 9, stdout="xoxb-private C:\\private", stderr=""
            )

        result = self.review.run_review(
            self.repo_root,
            expected_sha=self.EXPECTED_SHA,
            executor=executor,
            now="2026-08-15T12:00:00Z",
            platform="linux",
            python="python3",
        )

        self.assertEqual(set(result), {"commit", "reviewed_at", "checks"})
        self.assertEqual(result["commit"], self.EXPECTED_SHA)
        self.assertEqual(result["reviewed_at"], "2026-08-15T12:00:00Z")
        self.assertEqual(len(result["checks"]), 8)
        self.assertEqual(
            set(result["checks"][0]), {"id", "status", "duration_ms", "diagnostic"}
        )
        self.assertEqual(result["checks"][0]["diagnostic"], "Exited with code 9")
        self.assertNotIn("xoxb-private", json.dumps(result))
        self.assertTrue(all(kwargs["shell"] is False for _, kwargs in calls))
        self.assertTrue(all(kwargs["check"] is False for _, kwargs in calls))
        self.assertTrue(all(isinstance(argv, list) for argv, _ in calls))
        self.assertTrue((self.repo_root / ".production-review" / "logs" / "backend-tests.log").is_file())

    def test_run_review_uses_a_safe_timeout_diagnostic(self):
        def executor(argv, **kwargs):
            if tuple(argv) == ("git", "rev-parse", "HEAD"):
                return subprocess.CompletedProcess(argv, 0, stdout=self.EXPECTED_SHA + "\n", stderr="")
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output="private output")

        result = self.review.run_review(
            self.repo_root,
            expected_sha=self.EXPECTED_SHA,
            executor=executor,
            now="2026-08-15T12:00:00Z",
            platform="linux",
            python="python3",
        )

        self.assertEqual(result["checks"][0]["diagnostic"], "Timed out")

    def test_run_review_rejects_a_checked_out_commit_that_differs_from_expected(self):
        def executor(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, stdout="b" * 40 + "\n", stderr="")

        with self.assertRaisesRegex(
            ValueError, "^checked-out commit does not match expected SHA$"
        ):
            self.review.run_review(
                self.repo_root,
                expected_sha=self.EXPECTED_SHA,
                executor=executor,
                now="2026-08-15T12:00:00Z",
            )

    def test_run_review_caps_each_private_log_at_two_mebibytes(self):
        calls = 0

        def executor(argv, **kwargs):
            nonlocal calls
            if tuple(argv) == ("git", "rev-parse", "HEAD"):
                return subprocess.CompletedProcess(argv, 0, stdout=self.EXPECTED_SHA + "\n", stderr="")
            calls += 1
            output = "x" * (2 * 1024 * 1024 + 1) if calls == 1 else ""
            return subprocess.CompletedProcess(argv, 0, stdout=output, stderr="")

        self.review.run_review(
            self.repo_root,
            expected_sha=self.EXPECTED_SHA,
            executor=executor,
            now="2026-08-15T12:00:00Z",
        )

        log_path = self.repo_root / ".production-review" / "logs" / "backend-tests.log"
        self.assertEqual(log_path.stat().st_size, 2 * 1024 * 1024)

    def test_cli_writes_json_by_replacing_a_sibling_temporary_file(self):
        def executor(argv, **kwargs):
            if tuple(argv) == ("git", "rev-parse", "HEAD"):
                return subprocess.CompletedProcess(argv, 0, stdout=self.EXPECTED_SHA + "\n", stderr="")
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        replacements = []
        original_replace = Path.replace

        def recording_replace(source, target):
            replacements.append((source, target))
            return original_replace(source, target)

        with patch.object(Path, "replace", new=recording_replace):
            exit_code = self.review.main(
                ["run"],
                repo_root=self.repo_root,
                environ={"EXPECTED_SHA": self.EXPECTED_SHA},
                executor=executor,
                now="2026-08-15T12:00:00Z",
            )

        target = self.repo_root / ".production-review" / "deterministic.json"
        self.assertEqual(exit_code, 0)
        self.assertTrue(target.is_file())
        self.assertEqual(len(replacements), 1)
        self.assertEqual(replacements[0][0].parent, target.parent)
        self.assertEqual(replacements[0][1], target)


if __name__ == "__main__":
    unittest.main()
