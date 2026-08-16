import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("production_review_output.py")


def load_output_module():
    spec = importlib.util.spec_from_file_location("production_review_output", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("production review output module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def valid_ai_result(**finding_changes):
    finding = {
        "severity": "Important",
        "title": "Permission state can drift",
        "evidence": "backend/surveyor/permissions.py:42 lacks a recheck.",
        "file": "backend/surveyor/permissions.py",
        "line": 42,
        "recommendation": "Recheck canonical state before execution.",
    }
    finding.update(finding_changes)
    return json.dumps(
        {
            "summary": "One permission issue needs human validation.",
            "findings": [finding],
        }
    )


class ValidateAiResultTests(unittest.TestCase):
    def setUp(self):
        self.output = load_output_module()

    def test_accepts_only_the_bounded_schema(self):
        result = self.output.validate_ai_result(valid_ai_result())

        self.assertEqual(
            result,
            {
                "summary": "One permission issue needs human validation.",
                "findings": [
                    {
                        "severity": "Important",
                        "title": "Permission state can drift",
                        "evidence": "backend/surveyor/permissions.py:42 lacks a recheck.",
                        "file": "backend/surveyor/permissions.py",
                        "line": 42,
                        "recommendation": "Recheck canonical state before execution.",
                    }
                ],
            },
        )

    def test_rejects_malformed_or_non_exact_shapes(self):
        invalid_values = [
            None,
            "not json",
            json.dumps({"summary": "ok", "findings": [], "extra": True}),
            json.dumps({"summary": "ok"}),
            json.dumps({"summary": "ok", "findings": [{}]}),
            json.dumps(
                {
                    "summary": "ok",
                    "findings": [json.loads(valid_ai_result())["findings"][0]] * 6,
                }
            ),
        ]

        for value in invalid_values:
            with self.subTest(value=value):
                self.assertIsNone(self.output.validate_ai_result(value))

    def test_rejects_invalid_or_unsafe_finding_values_without_partial_cleanup(self):
        invalid_findings = [
            {"severity": "Urgent"},
            {"file": "backend/../secrets.py"},
            {"file": "/etc/passwd"},
            {"file": "backend\\permissions.py"},
            {"file": "C:/private/secret.txt"},
            {"file": "file:///private/secret.txt"},
            {"evidence": "xoxb-secret"},
            {"evidence": "ghp_secret"},
            {"evidence": "sk-ant-secret"},
            {"line": "42"},
            {"line": True},
            {"title": "x" * 121},
            {"evidence": "x" * 301},
            {"file": "a" * 201},
            {"recommendation": "x" * 301},
        ]

        for changes in invalid_findings:
            with self.subTest(changes=changes):
                self.assertIsNone(self.output.validate_ai_result(valid_ai_result(**changes)))

        overlong_summary = json.dumps(
            {"summary": "x" * 601, "findings": json.loads(valid_ai_result())["findings"]}
        )
        self.assertIsNone(self.output.validate_ai_result(overlong_summary))

    def test_rejects_unsafe_paths_and_urls_in_ai_text_but_keeps_ordinary_prose(self):
        unsafe_text = [
            "Inspect /srv/app before the next review.",
            "Send the result to mailto:ops@example.com.",
            "Read www.example.com for more details.",
            "Read example.com for more details.",
            "Read docs.example.com/start for more details.",
        ]
        for field in ("summary", "title"):
            for text in unsafe_text:
                with self.subTest(field=field, text=text):
                    value = json.loads(valid_ai_result())
                    if field == "summary":
                        value["summary"] = text
                    else:
                        value["findings"][0][field] = text
                    self.assertIsNone(self.output.validate_ai_result(json.dumps(value)))

        for field in ("summary", "title"):
            for text in (
                "Inspect the service configuration before merging.",
                "A www directory can hold static assets.",
                "Email the team after human validation.",
                "Review backend/surveyor/permissions.py before merging.",
                "Version 1.2.3 is ready for human validation.",
            ):
                with self.subTest(field=field, text=text):
                    value = json.loads(valid_ai_result())
                    if field == "summary":
                        value["summary"] = text
                    else:
                        value["findings"][0][field] = text
                    self.assertIsNotNone(self.output.validate_ai_result(json.dumps(value)))


class AssembleReviewTests(unittest.TestCase):
    COMMIT = "a" * 40

    def setUp(self):
        self.output = load_output_module()

    def deterministic(self, status="passed"):
        return {
            "commit": self.COMMIT,
            "reviewed_at": "2026-08-15T12:00:00Z",
            "checks": [
                {
                    "id": "backend-tests",
                    "status": status,
                    "duration_ms": 12,
                    "diagnostic": "Passed" if status == "passed" else "Exited with code 1",
                }
            ],
        }

    def button_urls(self, slack):
        return {
            element["text"]["text"]: element["url"]
            for block in slack["blocks"]
            if block["type"] == "actions"
            for element in block["elements"]
        }

    def test_deterministic_failure_always_wins_over_ai_availability(self):
        final, slack, markdown = self.output.assemble_review(
            self.deterministic("failed"),
            self.output.validate_ai_result(valid_ai_result()),
            anthropic_configured=True,
            run_id="123",
        )

        self.assertEqual(final["state"], "CHECKS FAILED")
        self.assertIn("CHECKS FAILED", json.dumps(slack))
        self.assertIn("CHECKS FAILED", markdown)
        self.assertIn("View failed checks", self.button_urls(slack))

    def test_passing_checks_and_valid_ai_produce_a_ready_review(self):
        final, slack, markdown = self.output.assemble_review(
            self.deterministic(),
            self.output.validate_ai_result(valid_ai_result()),
            anthropic_configured=True,
            run_id="123",
        )

        self.assertEqual(final["state"], "REVIEW READY")
        self.assertFalse(final["setup_required"])
        self.assertEqual(final["ai"]["findings"][0]["severity"], "Important")
        self.assertIn("REVIEW READY", json.dumps(slack))
        self.assertIn("REVIEW READY", markdown)
        self.assertNotIn("View failed checks", self.button_urls(slack))

    def test_absent_or_invalid_ai_produces_unavailable_review_and_setup_signal(self):
        for ai_result in (None, {"unexpected": "result"}):
            with self.subTest(ai_result=ai_result):
                final, _, _ = self.output.assemble_review(
                    self.deterministic(),
                    ai_result,
                    anthropic_configured=False,
                    run_id="123",
                )
                self.assertEqual(final["state"], "REVIEW UNAVAILABLE")
                self.assertTrue(final["setup_required"])
                self.assertIsNone(final["ai"])

    def test_slack_uses_only_fixed_urls_and_escapes_ai_text(self):
        escaped_ai = self.output.validate_ai_result(
            valid_ai_result(title="Use <recheck> & human review")
        )
        _, slack, _ = self.output.assemble_review(
            self.deterministic("failed"),
            escaped_ai,
            anthropic_configured=True,
            run_id="123",
        )

        self.assertEqual({block["type"] for block in slack["blocks"]}, {"section", "context", "actions"})
        urls = self.button_urls(slack)
        repository = "https://github.com/ItzJLaugh/Cordia"
        self.assertEqual(
            urls,
            {
                "Open full review": repository + "/actions/runs/123",
                "View commit": repository + "/commit/" + self.COMMIT,
                "Human review guide": repository
                + "/blob/"
                + self.COMMIT
                + "/docs/PRODUCTION_REVIEW_PLAYBOOK.md",
                "View failed checks": repository + "/actions/runs/123",
            },
        )
        slack_json = json.dumps(slack)
        self.assertIn("Use &lt;recheck&gt; &amp; human review", slack_json)
        self.assertNotIn("action_id", slack_json)
        self.assertNotIn("https://example.invalid", slack_json)
        self.assertNotIn("xoxb-private", slack_json)
        self.assertNotIn("C:\\private", slack_json)
        self.assertNotIn("SLACK_WEBHOOK_URL", slack_json)

    def test_cli_writes_all_artifacts_without_copying_an_invalid_ai_result(self):
        invalid_marker = "sk-ant-invalid-result-must-not-be-copied"
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            artifact_dir = repo_root / ".production-review"
            artifact_dir.mkdir()
            (artifact_dir / "deterministic.json").write_text(
                json.dumps(self.deterministic()), encoding="utf-8"
            )

            exit_code = self.output.main(
                ["assemble"],
                repo_root=repo_root,
                environ={
                    "AI_REVIEW_JSON": json.dumps(
                        {"summary": invalid_marker, "findings": [], "unknown": True}
                    ),
                    "ANTHROPIC_CONFIGURED": "true",
                    "GITHUB_RUN_ID": "123",
                },
            )

            final_path = artifact_dir / "final.json"
            slack_path = artifact_dir / "slack.json"
            markdown_path = artifact_dir / "review.md"
            self.assertEqual(exit_code, 0)
            self.assertTrue(final_path.is_file())
            self.assertTrue(slack_path.is_file())
            self.assertTrue(markdown_path.is_file())

            final = json.loads(final_path.read_text(encoding="utf-8"))
            artifacts = "\n".join(
                path.read_text(encoding="utf-8")
                for path in (final_path, slack_path, markdown_path)
            )
            self.assertEqual(final["state"], "REVIEW UNAVAILABLE")
            self.assertIsNone(final["ai"])
            self.assertNotIn(invalid_marker, artifacts)

    def test_cli_failure_removes_stale_and_partially_published_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            artifact_dir = repo_root / ".production-review"
            artifact_dir.mkdir()
            (artifact_dir / "deterministic.json").write_text(
                json.dumps(self.deterministic()), encoding="utf-8"
            )
            public_paths = tuple(
                artifact_dir / name
                for name in ("final.json", "slack.json", "review.md")
            )
            for path in public_paths:
                path.write_text("stale artifact", encoding="utf-8")

            original_replace = Path.replace

            def fail_slack_publish(source, target):
                if Path(target) == artifact_dir / "slack.json":
                    raise OSError("simulated publish failure")
                return original_replace(source, target)

            with patch.object(Path, "replace", new=fail_slack_publish):
                exit_code = self.output.main(
                    ["assemble"],
                    repo_root=repo_root,
                    environ={
                        "AI_REVIEW_JSON": valid_ai_result(),
                        "ANTHROPIC_CONFIGURED": "true",
                        "GITHUB_RUN_ID": "123",
                    },
                )

            self.assertEqual(exit_code, 2)
            self.assertTrue((artifact_dir / "deterministic.json").is_file())
            for path in public_paths:
                with self.subTest(path=path.name):
                    self.assertFalse(path.exists())
                    self.assertFalse(path.with_name(path.name + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
