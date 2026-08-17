import importlib.util
import json
import os
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
            {"evidence": "OPENAI_API_KEY=plain-sensitive-value"},
            {"evidence": "DATABASE_URL=plain-sensitive-value"},
            {"title": "-----BEGIN PRIVATE KEY-----"},
            {"recommendation": "Contact reviewer@internal.invalid"},
            {"line": "42"},
            {"line": True},
            {"line": 2_147_483_648},
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
            model_configured=True,
            model_succeeded=True,
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
            model_configured=True,
            model_succeeded=True,
            run_id="123",
        )

        self.assertEqual(final["state"], "REVIEW READY")
        self.assertFalse(final["setup_required"])
        self.assertEqual(final["ai"]["findings"][0]["severity"], "Important")
        self.assertIn("REVIEW READY", json.dumps(slack))
        self.assertIn("REVIEW READY", markdown)
        self.assertIn("AI advisory", json.dumps(slack))
        self.assertIn("AI advisory", markdown)
        self.assertNotIn("Claude advisory", json.dumps(slack))
        self.assertNotIn("Claude advisory", markdown)
        self.assertNotIn("View failed checks", self.button_urls(slack))

    def test_absent_or_invalid_ai_produces_unavailable_review_and_setup_signal(self):
        for ai_result in (None, {"unexpected": "result"}):
            with self.subTest(ai_result=ai_result):
                final, _, _ = self.output.assemble_review(
                    self.deterministic(),
                    ai_result,
                    model_configured=False,
                    model_succeeded=False,
                    run_id="123",
                )
                self.assertEqual(final["state"], "REVIEW UNAVAILABLE")
                self.assertTrue(final["setup_required"])
                self.assertIsNone(final["ai"])

    def test_model_configuration_and_execution_success_are_distinct(self):
        valid_ai = self.output.validate_ai_result(valid_ai_result())
        cases = (
            (True, False, False),
            (False, False, True),
            (False, True, True),
        )

        for configured, succeeded, setup_required in cases:
            with self.subTest(configured=configured, succeeded=succeeded):
                final, _, _ = self.output.assemble_review(
                    self.deterministic(),
                    valid_ai,
                    model_configured=configured,
                    model_succeeded=succeeded,
                    run_id="123",
                )

                self.assertEqual(final["state"], "REVIEW UNAVAILABLE")
                self.assertEqual(final["setup_required"], setup_required)
                self.assertIsNone(final["ai"])

    def test_slack_uses_only_fixed_urls_and_escapes_ai_text(self):
        escaped_ai = self.output.validate_ai_result(
            valid_ai_result(title="Use <recheck> & human review")
        )
        _, slack, _ = self.output.assemble_review(
            self.deterministic("failed"),
            escaped_ai,
            model_configured=True,
            model_succeeded=True,
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
        self.assertIn("`backend-tests`: failed", slack_json)
        self.assertIn("`backend/surveyor/permissions.py:42`", slack_json)
        self.assertNotIn("Exited with code 1", slack_json)
        self.assertNotIn("action_id", slack_json)
        self.assertNotIn("https://example.invalid", slack_json)
        self.assertNotIn("xoxb-private", slack_json)
        self.assertNotIn("C:\\private", slack_json)
        self.assertNotIn("SLACK_WEBHOOK_URL", slack_json)

    def test_slack_details_stay_within_block_limits_at_the_schema_maximum(self):
        finding = json.loads(valid_ai_result())['findings'][0]
        finding.update(
            {
                "title": "t" * 120,
                "evidence": "e" * 300,
                "file": "f" * 200,
                "line": 2_147_483_647,
                "recommendation": "r" * 300,
            }
        )
        ai_result = self.output.validate_ai_result(
            json.dumps({"summary": "s" * 600, "findings": [finding] * 5})
        )
        deterministic = self.deterministic()
        deterministic["checks"] = [
            {
                "id": check_id,
                "status": "passed",
                "duration_ms": 1,
                "diagnostic": "Passed",
            }
            for check_id in (
                "backend-tests",
                "dashboard-install",
                "dashboard-tests",
                "dashboard-build",
                "desktop-install",
                "desktop-tests",
                "dashboard-release",
                "commit-diff-check",
            )
        ]

        self.assertIsNotNone(ai_result)
        _, slack, _ = self.output.assemble_review(
            deterministic,
            ai_result,
            model_configured=True,
            model_succeeded=True,
            run_id="123",
        )

        for block in slack["blocks"]:
            if block["type"] == "section":
                self.assertLessEqual(len(block["text"]["text"]), 3000)
            if block["type"] == "context":
                for element in block["elements"]:
                    self.assertLessEqual(len(element["text"]), 2000)

    def test_deterministic_check_details_reject_unknown_duplicate_or_unsafe_values(self):
        invalid_checks = []
        for invalid_id in ("unknown-check", "C:\\private", "xoxb-private"):
            deterministic = self.deterministic()
            deterministic["checks"][0]["id"] = invalid_id
            invalid_checks.append(deterministic)

        duplicate = self.deterministic()
        duplicate["checks"] = duplicate["checks"] * 2
        invalid_checks.append(duplicate)

        unsafe_diagnostic = self.deterministic()
        unsafe_diagnostic["checks"][0]["diagnostic"] = "raw log xoxb-private"
        invalid_checks.append(unsafe_diagnostic)

        for deterministic in invalid_checks:
            with self.subTest(checks=deterministic["checks"]):
                with self.assertRaises(ValueError):
                    self.output.assemble_review(
                        deterministic,
                        None,
                        model_configured=False,
                        model_succeeded=False,
                        run_id="123",
                    )

    def test_cli_writes_unavailable_artifacts_without_copying_an_invalid_ai_file(self):
        invalid_marker = "invalid-openai-result-must-not-be-copied"
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            artifact_dir = repo_root / ".production-review"
            artifact_dir.mkdir()
            (artifact_dir / "deterministic.json").write_text(
                json.dumps(self.deterministic()), encoding="utf-8"
            )
            (artifact_dir / "openai-review.json").write_text(
                json.dumps({"summary": invalid_marker, "findings": [], "unknown": True}),
                encoding="utf-8",
            )

            exit_code = self.output.main(
                ["assemble"],
                repo_root=repo_root,
                environ={
                    "AI_REVIEW_PATH": ".production-review/openai-review.json",
                    "MODEL_REVIEW_CONFIGURED": "true",
                    "MODEL_REVIEW_SUCCEEDED": "true",
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

    def test_cli_treats_an_absent_ai_file_as_an_unavailable_review(self):
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
                    "AI_REVIEW_PATH": ".production-review/openai-review.json",
                    "MODEL_REVIEW_CONFIGURED": "true",
                    "MODEL_REVIEW_SUCCEEDED": "true",
                    "GITHUB_RUN_ID": "123",
                },
            )

            final = json.loads((artifact_dir / "final.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(final["state"], "REVIEW UNAVAILABLE")
            self.assertIsNone(final["ai"])

    def test_cli_fails_closed_for_symlinked_public_artifact_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            external_dir = repo_root / "external"
            external_dir.mkdir()
            (external_dir / "deterministic.json").write_text(
                json.dumps(self.deterministic()), encoding="utf-8"
            )
            external_final = external_dir / "final.json"
            external_final.write_text("keep external final", encoding="utf-8")
            artifact_dir = repo_root / ".production-review"
            try:
                artifact_dir.symlink_to(external_dir, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symbolic links are unavailable: {error}")

            exit_code = self.output.main(
                ["assemble"], repo_root=repo_root, environ={"GITHUB_RUN_ID": "123"}
            )

            self.assertEqual(exit_code, 2)
            self.assertTrue(artifact_dir.is_symlink())
            self.assertEqual(external_final.read_text(encoding="utf-8"), "keep external final")

        for unsafe_name in ("final.json", "final.json.tmp"):
            with self.subTest(unsafe_name=unsafe_name):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    repo_root = Path(temporary_directory)
                    artifact_dir = repo_root / ".production-review"
                    artifact_dir.mkdir()
                    (artifact_dir / "deterministic.json").write_text(
                        json.dumps(self.deterministic()), encoding="utf-8"
                    )
                    external_file = repo_root / "external-file.json"
                    external_file.write_text("keep external file", encoding="utf-8")
                    unsafe_path = artifact_dir / unsafe_name
                    try:
                        unsafe_path.symlink_to(external_file)
                    except OSError as error:
                        self.skipTest(f"symbolic links are unavailable: {error}")

                    exit_code = self.output.main(
                        ["assemble"], repo_root=repo_root, environ={"GITHUB_RUN_ID": "123"}
                    )

                    self.assertEqual(exit_code, 2)
                    self.assertTrue(unsafe_path.is_symlink())
                    self.assertEqual(
                        external_file.read_text(encoding="utf-8"), "keep external file"
                    )

    def test_cli_rejects_outside_or_symlinked_atomic_temp_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            artifact_dir = repo_root / ".production-review"
            artifact_dir.mkdir()
            (artifact_dir / "deterministic.json").write_text(
                json.dumps(self.deterministic()), encoding="utf-8"
            )
            outside_path = repo_root / "outside-temp"
            outside_path.write_text("keep outside temp", encoding="utf-8")

            def outside_temp(*args, **kwargs):
                return os.open(outside_path, os.O_RDWR), str(outside_path)

            with patch("tempfile.mkstemp", side_effect=outside_temp):
                exit_code = self.output.main(
                    ["assemble"], repo_root=repo_root, environ={"GITHUB_RUN_ID": "123"}
                )

            self.assertEqual(exit_code, 2)
            self.assertEqual(outside_path.read_text(encoding="utf-8"), "keep outside temp")

        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            artifact_dir = repo_root / ".production-review"
            artifact_dir.mkdir()
            (artifact_dir / "deterministic.json").write_text(
                json.dumps(self.deterministic()), encoding="utf-8"
            )
            external_path = repo_root / "external-temp-target"
            external_path.write_text("keep external target", encoding="utf-8")
            symlink_temp = artifact_dir / ".forced-temp"
            descriptor_path = repo_root / "descriptor-file"
            descriptor_path.write_text("keep descriptor", encoding="utf-8")
            try:
                symlink_temp.symlink_to(external_path)
            except OSError as error:
                self.skipTest(f"symbolic links are unavailable: {error}")

            def symlinked_temp(*args, **kwargs):
                return os.open(descriptor_path, os.O_RDWR), str(symlink_temp)

            with patch("tempfile.mkstemp", side_effect=symlinked_temp):
                exit_code = self.output.main(
                    ["assemble"], repo_root=repo_root, environ={"GITHUB_RUN_ID": "123"}
                )

            self.assertEqual(exit_code, 2)
            self.assertTrue(symlink_temp.is_symlink())
            self.assertEqual(external_path.read_text(encoding="utf-8"), "keep external target")

    def test_cli_loads_a_valid_bounded_ai_file_when_the_model_ran(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            artifact_dir = repo_root / ".production-review"
            artifact_dir.mkdir()
            (artifact_dir / "deterministic.json").write_text(
                json.dumps(self.deterministic()), encoding="utf-8"
            )
            (artifact_dir / "openai-review.json").write_text(
                valid_ai_result(), encoding="utf-8"
            )

            exit_code = self.output.main(
                ["assemble"],
                repo_root=repo_root,
                environ={
                    "AI_REVIEW_PATH": ".production-review/openai-review.json",
                    "MODEL_REVIEW_CONFIGURED": "true",
                    "MODEL_REVIEW_SUCCEEDED": "true",
                    "GITHUB_RUN_ID": "123",
                },
            )

            final = json.loads((artifact_dir / "final.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(final["state"], "REVIEW READY")
            self.assertEqual(final["ai"]["summary"], "One permission issue needs human validation.")

    def test_cli_never_loads_a_stale_ai_file_when_model_was_skipped_or_failed(self):
        cases = (
            ("false", "false", True),
            ("true", "false", False),
        )

        for configured, succeeded, setup_required in cases:
            with self.subTest(configured=configured, succeeded=succeeded):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    repo_root = Path(temporary_directory)
                    artifact_dir = repo_root / ".production-review"
                    artifact_dir.mkdir()
                    (artifact_dir / "deterministic.json").write_text(
                        json.dumps(self.deterministic()), encoding="utf-8"
                    )
                    (artifact_dir / "openai-review.json").write_text(
                        valid_ai_result(), encoding="utf-8"
                    )

                    with patch.object(
                        self.output,
                        "_load_ai_review",
                        side_effect=AssertionError("stale AI file must not be loaded"),
                    ):
                        exit_code = self.output.main(
                            ["assemble"],
                            repo_root=repo_root,
                            environ={
                                "AI_REVIEW_PATH": ".production-review/openai-review.json",
                                "MODEL_REVIEW_CONFIGURED": configured,
                                "MODEL_REVIEW_SUCCEEDED": succeeded,
                                "GITHUB_RUN_ID": "123",
                            },
                        )

                    final = json.loads((artifact_dir / "final.json").read_text(encoding="utf-8"))
                    self.assertEqual(exit_code, 0)
                    self.assertEqual(final["state"], "REVIEW UNAVAILABLE")
                    self.assertEqual(final["setup_required"], setup_required)
                    self.assertIsNone(final["ai"])

    def test_cli_checks_ai_file_symlinks_before_resolution(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            artifact_dir = repo_root / ".production-review"
            artifact_dir.mkdir()
            (artifact_dir / "deterministic.json").write_text(
                json.dumps(self.deterministic()), encoding="utf-8"
            )
            external_ai = repo_root / "external-ai.json"
            external_ai.write_text(valid_ai_result(), encoding="utf-8")
            ai_path = artifact_dir / "openai-review.json"
            try:
                ai_path.symlink_to(external_ai)
            except OSError as error:
                self.skipTest(f"symbolic links are unavailable: {error}")

            exit_code = self.output.main(
                ["assemble"],
                repo_root=repo_root,
                environ={
                    "AI_REVIEW_PATH": ".production-review/openai-review.json",
                    "MODEL_REVIEW_CONFIGURED": "true",
                    "MODEL_REVIEW_SUCCEEDED": "true",
                    "GITHUB_RUN_ID": "123",
                },
            )

            final = json.loads((artifact_dir / "final.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(final["state"], "REVIEW UNAVAILABLE")
            self.assertIsNone(final["ai"])

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
                        "AI_REVIEW_PATH": ".production-review/openai-review.json",
                        "MODEL_REVIEW_CONFIGURED": "true",
                        "MODEL_REVIEW_SUCCEEDED": "true",
                        "GITHUB_RUN_ID": "123",
                    },
                )

            self.assertEqual(exit_code, 2)
            self.assertTrue((artifact_dir / "deterministic.json").is_file())
            for path in public_paths:
                with self.subTest(path=path.name):
                    self.assertFalse(path.exists())
                    self.assertFalse(path.with_name(path.name + ".tmp").exists())

    def test_cli_publishes_each_artifact_from_a_unique_same_directory_temp(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            artifact_dir = repo_root / ".production-review"
            artifact_dir.mkdir()
            (artifact_dir / "deterministic.json").write_text(
                json.dumps(self.deterministic()), encoding="utf-8"
            )
            replacements = []
            original_replace = Path.replace

            def recording_replace(source, target):
                replacements.append((Path(source), Path(target)))
                return original_replace(source, target)

            with patch.object(Path, "replace", new=recording_replace):
                exit_code = self.output.main(
                    ["assemble"], repo_root=repo_root, environ={"GITHUB_RUN_ID": "123"}
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(len(replacements), 3)
            self.assertEqual(len({source.name for source, _ in replacements}), 3)
            for source, target in replacements:
                with self.subTest(target=target.name):
                    self.assertEqual(source.parent, target.parent)
                    self.assertNotEqual(source.name, target.name + ".tmp")

    def test_cli_cleanup_attempts_every_public_path_after_one_unlink_error(self):
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
                path.with_name(path.name + ".tmp").write_text(
                    "stale temporary artifact", encoding="utf-8"
                )

            locked_path = public_paths[0]
            attempted = []
            original_unlink = Path.unlink

            def fail_one_unlink(path, *, missing_ok=False):
                attempted.append(Path(path))
                if Path(path) == locked_path:
                    raise OSError("simulated locked artifact")
                return original_unlink(path, missing_ok=missing_ok)

            with patch.object(Path, "unlink", new=fail_one_unlink):
                exit_code = self.output.main(
                    ["assemble"],
                    repo_root=repo_root,
                    environ={
                        "AI_REVIEW_PATH": ".production-review/openai-review.json",
                        "MODEL_REVIEW_CONFIGURED": "true",
                        "MODEL_REVIEW_SUCCEEDED": "true",
                        "GITHUB_RUN_ID": "123",
                    },
                )

            expected_attempts = {
                candidate
                for path in public_paths
                for candidate in (path, path.with_name(path.name + ".tmp"))
            }
            self.assertEqual(exit_code, 2)
            self.assertTrue(expected_attempts.issubset(set(attempted)))
            self.assertTrue(locked_path.exists())
            for path in expected_attempts - {locked_path}:
                with self.subTest(path=path.name):
                    self.assertFalse(path.exists())

    def test_cli_cleanup_covers_unique_temp_files_and_fails_closed_on_a_temp_symlink(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            artifact_dir = repo_root / ".production-review"
            artifact_dir.mkdir()
            (artifact_dir / "deterministic.json").write_text(
                json.dumps(self.deterministic()), encoding="utf-8"
            )
            stale_temps = tuple(
                artifact_dir / f".{name}-stale.tmp"
                for name in ("final.json", "slack.json", "review.md")
            )
            for path in stale_temps:
                path.write_text("stale temporary data", encoding="utf-8")

            exit_code = self.output.main(
                ["assemble"], repo_root=repo_root, environ={"GITHUB_RUN_ID": "invalid"}
            )

            self.assertEqual(exit_code, 2)
            for path in stale_temps:
                with self.subTest(path=path.name):
                    self.assertFalse(path.exists())

        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            artifact_dir = repo_root / ".production-review"
            artifact_dir.mkdir()
            (artifact_dir / "deterministic.json").write_text(
                json.dumps(self.deterministic()), encoding="utf-8"
            )
            external = repo_root / "external-temp-target"
            external.write_text("keep external target", encoding="utf-8")
            stale_symlink = artifact_dir / ".final.json-attacker.tmp"
            try:
                stale_symlink.symlink_to(external)
            except OSError as error:
                self.skipTest(f"symbolic links are unavailable: {error}")

            exit_code = self.output.main(
                ["assemble"], repo_root=repo_root, environ={"GITHUB_RUN_ID": "123"}
            )

            self.assertEqual(exit_code, 2)
            self.assertTrue(stale_symlink.is_symlink())
            self.assertEqual(external.read_text(encoding="utf-8"), "keep external target")


if __name__ == "__main__":
    unittest.main()
