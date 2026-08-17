from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("openai_production_review.py")
SHA = "a" * 40
API_KEY = "sk-test-private-value"


def load_module():
    spec = importlib.util.spec_from_file_location("openai_production_review", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("OpenAI production reviewer module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def valid_ai_object():
    return {
        "summary": "One bounded finding needs human validation.",
        "findings": [
            {
                "severity": "Important",
                "title": "Review the permission check",
                "evidence": "The changed branch reaches the approval path.",
                "file": "src/safe.py",
                "line": 4,
                "recommendation": "Confirm permission before deployment.",
            }
        ],
    }


class OpenAiProductionReviewTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.artifact_dir = self.root / ".production-review"
        self.artifact_dir.mkdir()
        (self.artifact_dir / "deterministic.json").write_text(
            json.dumps(
                {
                    "commit": SHA,
                    "reviewed_at": "2026-08-16T12:00:00Z",
                    "checks": [
                        {
                            "id": "backend-tests",
                            "status": "passed",
                            "duration_ms": 12,
                            "diagnostic": "Passed",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        source = self.root / "src"
        source.mkdir()
        (source / "safe.py").write_text("def safe():\n    return 'ok'\n", encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()
        sys.modules.pop("openai_production_review", None)

    def fake_git(self, argv, **kwargs):
        command = tuple(argv)
        if command == ("git", "rev-parse", "HEAD"):
            return subprocess.CompletedProcess(argv, 0, SHA + "\n", "")
        if command == ("git", "status", "--porcelain", "--untracked-files=no"):
            return subprocess.CompletedProcess(argv, 0, "", "")
        if command == ("git", "diff", "--no-ext-diff", "--unified=3", "HEAD^", "HEAD", "--"):
            return subprocess.CompletedProcess(
                argv,
                0,
                "diff --git a/src/safe.py b/src/safe.py\n@@ -1 +1 @@\n-old\n+new\n"
                "diff --git a/ignored.bin b/ignored.bin\nBinary files differ\n",
                "",
            )
        if command == ("git", "diff", "--name-only", "HEAD^", "HEAD", "--"):
            return subprocess.CompletedProcess(argv, 0, "src/safe.py\nignored.bin\n", "")
        if command == ("git", "diff", "--diff-filter=D", "--name-only", "HEAD^", "HEAD", "--"):
            return subprocess.CompletedProcess(argv, 0, "", "")
        if command == ("git", "show", f"{SHA}:src/safe.py"):
            return subprocess.CompletedProcess(argv, 0, b"def safe():\n    return 'ok'\n", b"")
        if command == ("git", "show", f"{SHA}:ignored.bin"):
            return subprocess.CompletedProcess(argv, 0, b"\x00binary", b"")
        raise AssertionError(f"unexpected Git command: {argv!r}")

    def make_symlink(self, path, target):
        try:
            path.symlink_to(target)
        except OSError as error:
            self.skipTest(f"symbolic links are unavailable: {error}")

    def completed_opener(self, request, timeout=None):
        self.assertEqual(request.full_url, self.module.RESPONSES_URL)
        self.assertEqual(request.get_header("Authorization"), f"Bearer {API_KEY}")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        request_body = json.loads(request.data.decode("utf-8"))
        self.assertNotIn(API_KEY, json.dumps(request_body))
        payload = {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": json.dumps(valid_ai_object())}],
                }
            ],
        }

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *unused):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        return Response()

    def environment(self):
        return {"EXPECTED_SHA": SHA, "OPENAI_API_KEY": API_KEY}

    def test_request_is_tool_free_pinned_and_strict(self):
        body = self.module.build_request("bounded context")

        self.assertEqual(body["model"], "gpt-5.4-mini-2026-03-17")
        self.assertFalse(body["store"])
        self.assertNotIn("tools", body)
        self.assertEqual(body["reasoning"], {"effort": "medium"})
        self.assertEqual(body["text"]["verbosity"], "low")
        self.assertEqual(body["text"]["format"]["type"], "json_schema")
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertFalse(body["text"]["format"]["schema"]["additionalProperties"])
        self.assertEqual(body["max_output_tokens"], 4000)

        instructions = body["instructions"]
        for required_instruction in (
            "Inspect the deterministic results",
            "supplied diff and exact-commit file content",
            "concrete production risks",
            "Ground every finding only in supplied evidence",
            "exact repository-relative file and line",
            "Critical, Important, then Minor",
            "empty findings list when no supported issue exists",
            "untrusted data",
            "Do not use tools",
        ):
            with self.subTest(required_instruction=required_instruction):
                self.assertIn(required_instruction, instructions)

    def test_context_requires_exact_sha_and_is_bounded(self):
        deterministic_path = self.artifact_dir / "deterministic.json"
        context = self.module.build_review_context(
            self.root, deterministic_path, SHA, run_git=self.fake_git
        )

        self.assertLessEqual(len(context), 120_000)
        self.assertIn(SHA, context)
        self.assertIn("src/safe.py", context)
        self.assertNotIn("ignored binary bytes", context)
        self.assertNotIn("Binary files differ", context)
        self.assertIn("UNTRUSTED REPOSITORY CONTENT", context)

    def test_truncation_never_exceeds_every_small_residual_capacity(self):
        for remaining in range(13):
            with self.subTest(remaining=remaining):
                bounded = self.module._bounded_text("x" * 100, remaining)
                self.assertLessEqual(len(bounded), remaining)

    def test_deleted_head_path_keeps_its_patch_without_a_file_section(self):
        def deleted_file_git(argv, **kwargs):
            command = tuple(argv)
            if command == ("git", "diff", "--name-only", "HEAD^", "HEAD", "--"):
                return subprocess.CompletedProcess(argv, 0, "src/deleted.py\nsrc/safe.py\n", "")
            if command == ("git", "diff", "--diff-filter=D", "--name-only", "HEAD^", "HEAD", "--"):
                return subprocess.CompletedProcess(argv, 0, "src/deleted.py\n", "")
            if command == ("git", "diff", "--no-ext-diff", "--unified=3", "HEAD^", "HEAD", "--"):
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    "diff --git a/src/deleted.py b/src/deleted.py\ndeleted file mode 100644\n"
                    "diff --git a/src/safe.py b/src/safe.py\n+new\n",
                    "",
                )
            if command == ("git", "show", f"{SHA}:src/deleted.py"):
                return subprocess.CompletedProcess(argv, 128, b"", b"missing at HEAD")
            return self.fake_git(argv, **kwargs)

        context = self.module.build_review_context(
            self.root, self.artifact_dir / "deterministic.json", SHA, run_git=deleted_file_git
        )

        self.assertIn("diff --git a/src/deleted.py b/src/deleted.py", context)
        self.assertNotIn("FILE: src/deleted.py", context)
        self.assertIn("FILE: src/safe.py", context)

    def test_context_excludes_private_paths_caps_files_and_handles_malformed_text(self):
        (self.root / ".env").write_text("OPENAI_API_KEY=never-copy", encoding="utf-8")
        (self.root / "deploy_key.pem").write_text("PRIVATE KEY", encoding="utf-8")
        (self.root / "src" / "invalid.py").write_bytes(b"text before\xff text after")
        for number in range(self.module.MAX_CHANGED_FILES + 3):
            (self.root / "src" / f"changed{number}.py").write_text(
                "x" * (self.module.MAX_FILE_CHARS + 100), encoding="utf-8"
            )

        names = ["src/invalid.py", ".env", "deploy_key.pem"] + [
            f"src/changed{number}.py" for number in range(self.module.MAX_CHANGED_FILES + 3)
        ]

        def git_with_many_files(argv, **kwargs):
            if tuple(argv) == ("git", "diff", "--name-only", "HEAD^", "HEAD", "--"):
                return subprocess.CompletedProcess(argv, 0, "\n".join(names) + "\n", "")
            if tuple(argv) == ("git", "diff", "--no-ext-diff", "--unified=3", "HEAD^", "HEAD", "--"):
                return subprocess.CompletedProcess(argv, 0, "", "")
            if tuple(argv) == ("git", "show", f"{SHA}:src/invalid.py"):
                return subprocess.CompletedProcess(argv, 0, b"text before\xff text after", b"")
            if tuple(argv)[:2] == ("git", "show"):
                return subprocess.CompletedProcess(argv, 0, b"x" * (self.module.MAX_FILE_CHARS + 100), b"")
            return self.fake_git(argv, **kwargs)

        context = self.module.build_review_context(
            self.root, self.artifact_dir / "deterministic.json", SHA, run_git=git_with_many_files
        )

        self.assertNotIn("never-copy", context)
        self.assertNotIn("PRIVATE KEY", context)
        self.assertNotIn(".env", context)
        self.assertNotIn("deploy_key.pem", context)
        self.assertIn("text before", context)
        self.assertLessEqual(context.count("FILE: src/changed"), self.module.MAX_CHANGED_FILES)
        self.assertLessEqual(len(context), self.module.MAX_CONTEXT_CHARS)

    def test_sensitive_diff_and_exact_commit_blob_lines_are_redacted_before_request(self):
        sensitive_values = (
            "ghp_DIFF_SENTINEL_1234567890",
            "diff-owner@example.invalid",
            "C:\\Users\\diff-owner\\private.txt",
            "diff-secret-assignment",
            "diff-database-secret",
            "DIFF_PRIVATE_KEY_BODY_SENTINEL",
            "ghp_BLOB_SENTINEL_1234567890",
            "blob-owner@example.invalid",
            "/home/blob-owner/private.txt",
            "blob-secret-assignment",
            "blob-connection-secret",
            "/srv/cordia/private.txt",
            "BLOB_PRIVATE_KEY_BODY_SENTINEL",
            "SENSITIVE_DIRECTORY_SENTINEL",
        )

        diff = "".join(
            (
                "diff --git a/src/safe.py b/src/safe.py\n",
                "@@ -1,2 +1,8 @@\n",
                "+safe neighboring diff line\n",
                "+token = 'ghp_DIFF_SENTINEL_1234567890'\n",
                "+contact = 'diff-owner@example.invalid'\n",
                "+path = r'C:\\Users\\diff-owner\\private.txt'\n",
                "+OPENAI_API_KEY=diff-secret-assignment\n",
                "+\"DATABASE_URL\": \"diff-database-secret\"\n",
                "+-----BEGIN PRIVATE KEY-----\n",
                "+DIFF_PRIVATE_KEY_BODY_SENTINEL\n",
                "+-----END PRIVATE KEY-----\n",
                "diff --git a/secrets/config.py b/secrets/config.py\n",
                "@@ -0,0 +1 @@\n",
                "+SENSITIVE_DIRECTORY_SENTINEL\n",
            )
        )
        blob = "".join(
            (
                "safe_before = True\n",
                "token = 'ghp_BLOB_SENTINEL_1234567890'\n",
                "contact = 'blob-owner@example.invalid'\n",
                "path = '/home/blob-owner/private.txt'\n",
                "password: blob-secret-assignment\n",
                "connection_string = 'blob-connection-secret'\n",
                "server_path = '/srv/cordia/private.txt'\n",
                "-----BEGIN PRIVATE KEY-----\n",
                "BLOB_PRIVATE_KEY_BODY_SENTINEL\n",
                "-----END PRIVATE KEY-----\n",
                "safe_after = True\n",
            )
        ).encode("utf-8")

        def sensitive_git(argv, **kwargs):
            command = tuple(argv)
            if command == ("git", "diff", "--name-only", "HEAD^", "HEAD", "--"):
                return subprocess.CompletedProcess(argv, 0, "src/safe.py\nsecrets/config.py\n", "")
            if command == ("git", "diff", "--no-ext-diff", "--unified=3", "HEAD^", "HEAD", "--"):
                return subprocess.CompletedProcess(argv, 0, diff, "")
            if command == ("git", "show", f"{SHA}:src/safe.py"):
                return subprocess.CompletedProcess(argv, 0, blob, b"")
            if command == ("git", "show", f"{SHA}:secrets/config.py"):
                return subprocess.CompletedProcess(argv, 0, b"SENSITIVE_DIRECTORY_SENTINEL\n", b"")
            return self.fake_git(argv, **kwargs)

        captured_request = {}

        def capturing_opener(request, timeout=None):
            captured_request.update(json.loads(request.data.decode("utf-8")))
            return self.completed_opener(request, timeout=timeout)

        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = self.module.main(
                ["run"],
                repo_root=self.root,
                environ=self.environment(),
                opener=capturing_opener,
                run_git=sensitive_git,
            )

        output_text = (self.artifact_dir / "openai-review.json").read_text(encoding="utf-8")
        observable_text = "\n".join(
            (json.dumps(captured_request), stdout.getvalue(), stderr.getvalue(), output_text)
        )
        self.assertEqual(exit_code, 0)
        self.assertIn("safe neighboring diff line", captured_request["input"])
        self.assertIn("safe_before = True", captured_request["input"])
        self.assertIn("safe_after = True", captured_request["input"])
        self.assertIn("[REDACTED SENSITIVE LINE]", captured_request["input"])
        self.assertNotIn("secrets/config.py", captured_request["input"])
        for sensitive_value in sensitive_values:
            with self.subTest(sensitive_value=sensitive_value):
                self.assertNotIn(sensitive_value, observable_text)

    def test_common_credential_formats_and_private_dotfiles_never_enter_context(self):
        private_paths = (
            ".npmrc",
            ".netrc",
            ".pypirc",
            ".git-credentials",
            ".pgpass",
        )
        for path in private_paths:
            with self.subTest(path=path):
                self.assertTrue(self.module._is_private_path(path))

        sensitive_values = (
            "npm_REVIEW_SENTINEL_1234567890",
            "sk_live_REVIEW_SENTINEL_1234567890",
            "eyJhbGciOiJIUzI1NiJ9.REVIEW_SENTINEL.signature",
            "refresh-token-review-sentinel",
            "netrc-review-sentinel",
            "multiline-review-sentinel",
        )
        unsafe_source = "".join(
            (
                "_authToken=npm_REVIEW_SENTINEL_1234567890\n",
                "stripe = 'sk_live_REVIEW_SENTINEL_1234567890'\n",
                "jwt = 'eyJhbGciOiJIUzI1NiJ9.REVIEW_SENTINEL.signature'\n",
                "refreshToken: refresh-token-review-sentinel\n",
                "password netrc-review-sentinel\n",
                "password = (\n",
                "    'multiline-review-sentinel'\n",
                ")\n",
            )
        )

        redacted = self.module._redact_sensitive_lines(unsafe_source)

        self.assertIn(self.module.REDACTION_MARKER, redacted)
        for sensitive_value in sensitive_values:
            with self.subTest(sensitive_value=sensitive_value):
                self.assertNotIn(sensitive_value, redacted)

    def test_invalid_deterministic_schema_never_reaches_the_opener(self):
        valid = json.loads((self.artifact_dir / "deterministic.json").read_text(encoding="utf-8"))
        invalid_values = []

        unknown_top_level = dict(valid)
        unknown_top_level["raw_output"] = "OPENAI_API_KEY=must-not-send"
        invalid_values.append(unknown_top_level)

        unsafe_timestamp = json.loads(json.dumps(valid))
        unsafe_timestamp["reviewed_at"] = "review-owner@example.invalid"
        invalid_values.append(unsafe_timestamp)

        unknown_check_field = json.loads(json.dumps(valid))
        unknown_check_field["checks"][0]["raw_log"] = "ghp_MUST_NOT_SEND"
        invalid_values.append(unknown_check_field)

        unsafe_diagnostic = json.loads(json.dumps(valid))
        unsafe_diagnostic["checks"][0]["diagnostic"] = "OPENAI_API_KEY=must-not-send"
        invalid_values.append(unsafe_diagnostic)

        for deterministic in invalid_values:
            with self.subTest(deterministic=deterministic):
                (self.artifact_dir / "deterministic.json").write_text(
                    json.dumps(deterministic), encoding="utf-8"
                )
                opener_calls = []

                def forbidden_opener(*args, **kwargs):
                    opener_calls.append((args, kwargs))
                    return self.completed_opener(*args, **kwargs)

                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = self.module.main(
                        ["run"],
                        repo_root=self.root,
                        environ=self.environment(),
                        opener=forbidden_opener,
                        run_git=self.fake_git,
                    )

                self.assertEqual(exit_code, 2)
                self.assertEqual(opener_calls, [])
                self.assertFalse((self.artifact_dir / "openai-review.json").exists())
                self.assertNotIn("must-not-send", stdout.getvalue() + stderr.getvalue())

    def test_context_rejects_mismatched_or_invalid_sha(self):
        with self.assertRaises(ValueError):
            self.module.build_review_context(
                self.root, self.artifact_dir / "deterministic.json", "A" * 40, run_git=self.fake_git
            )
        with self.assertRaises(ValueError):
            self.module.build_review_context(
                self.root, self.artifact_dir / "deterministic.json", "not-a-sha", run_git=self.fake_git
            )

    def test_context_reads_changed_content_from_the_verified_commit_not_worktree(self):
        (self.root / "src" / "safe.py").write_text("OPENAI_API_KEY=dirty-secret", encoding="utf-8")

        def committed_blob_git(argv, **kwargs):
            if tuple(argv) == ("git", "show", f"{SHA}:src/safe.py"):
                return subprocess.CompletedProcess(argv, 0, b"def committed():\n    return 'safe'\n", b"")
            return self.fake_git(argv, **kwargs)

        context = self.module.build_review_context(
            self.root, self.artifact_dir / "deterministic.json", SHA, run_git=committed_blob_git
        )

        self.assertIn("def committed()", context)
        self.assertNotIn("dirty-secret", context)

    def test_context_fails_closed_for_a_dirty_worktree_or_changed_symlink(self):
        def dirty_git(argv, **kwargs):
            if tuple(argv) == ("git", "status", "--porcelain", "--untracked-files=no"):
                return subprocess.CompletedProcess(argv, 0, " M src/safe.py\n", "")
            return self.fake_git(argv, **kwargs)

        with self.assertRaises(ValueError):
            self.module.build_review_context(
                self.root, self.artifact_dir / "deterministic.json", SHA, run_git=dirty_git
            )

        (self.root / ".env").write_text("OPENAI_API_KEY=symlink-secret", encoding="utf-8")
        linked_path = self.root / "src" / "linked.py"
        self.make_symlink(linked_path, self.root / ".env")

        def symlink_git(argv, **kwargs):
            if tuple(argv) == ("git", "diff", "--name-only", "HEAD^", "HEAD", "--"):
                return subprocess.CompletedProcess(argv, 0, "src/linked.py\n", "")
            if tuple(argv) == ("git", "show", f"{SHA}:src/linked.py"):
                return subprocess.CompletedProcess(argv, 0, b".env\n", b"")
            return self.fake_git(argv, **kwargs)

        with self.assertRaises(ValueError):
            self.module.build_review_context(
                self.root, self.artifact_dir / "deterministic.json", SHA, run_git=symlink_git
            )

    def test_context_bounds_each_section_and_preserves_delimiters(self):
        def oversized_git(argv, **kwargs):
            if tuple(argv) == ("git", "diff", "--no-ext-diff", "--unified=3", "HEAD^", "HEAD", "--"):
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    "diff --git a/src/safe.py b/src/safe.py\n" + "+d" * 40_000,
                    "",
                )
            if tuple(argv) == ("git", "show", f"{SHA}:src/safe.py"):
                return subprocess.CompletedProcess(argv, 0, b"x" * 50_000, b"")
            return self.fake_git(argv, **kwargs)

        context = self.module.build_review_context(
            self.root, self.artifact_dir / "deterministic.json", SHA, run_git=oversized_git
        )

        self.assertLessEqual(len(context), self.module.MAX_CONTEXT_CHARS)
        self.assertIn(f"EXPECTED_SHA: {SHA}", context)
        self.assertIn("<DIFF>", context)
        self.assertIn("</DIFF>", context)
        self.assertIn("</DETERMINISTIC_REVIEW>", context)
        self.assertTrue(context.endswith("</UNTRUSTED_REPOSITORY_CONTENT>\n"))

    def test_context_rejects_traversal_and_safely_handles_percent_and_unicode_names(self):
        def unusual_name_git(argv, **kwargs):
            if tuple(argv) == ("git", "diff", "--name-only", "HEAD^", "HEAD", "--"):
                return subprocess.CompletedProcess(
                    argv, 0, "src/safe.py\nsrc/../.env\nsrc/100%name.py\nsrc/unicode-☃.py\n", ""
                )
            if tuple(argv) == ("git", "show", f"{SHA}:src/safe.py"):
                return subprocess.CompletedProcess(argv, 0, "snowman ☃ and 100% text".encode("utf-8"), b"")
            return self.fake_git(argv, **kwargs)

        context = self.module.build_review_context(
            self.root, self.artifact_dir / "deterministic.json", SHA, run_git=unusual_name_git
        )

        self.assertIn("snowman ☃ and 100% text", context)
        self.assertNotIn("src/../.env", context)
        self.assertNotIn("src/100%name.py", context)
        self.assertNotIn("src/unicode-☃.py", context)

    def test_context_rejects_an_isolated_checked_out_head_mismatch(self):
        def mismatched_head_git(argv, **kwargs):
            if tuple(argv) == ("git", "rev-parse", "HEAD"):
                return subprocess.CompletedProcess(argv, 0, "b" * 40 + "\n", "")
            return self.fake_git(argv, **kwargs)

        with self.assertRaises(ValueError):
            self.module.build_review_context(
                self.root, self.artifact_dir / "deterministic.json", SHA, run_git=mismatched_head_git
            )

    def test_completed_response_writes_only_validated_result(self):
        exit_code = self.module.main(
            ["run"],
            repo_root=self.root,
            environ=self.environment(),
            opener=self.completed_opener,
            run_git=self.fake_git,
        )

        output_path = self.artifact_dir / "openai-review.json"
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), valid_ai_object())

    def test_api_failure_and_invalid_response_fail_closed_without_leakage(self):
        output_path = self.artifact_dir / "openai-review.json"
        output_path.write_text("stale", encoding="utf-8")

        def failing_opener(request, timeout=None):
            raise OSError(f"network rejected {API_KEY}")

        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = self.module.main(
                ["run"],
                repo_root=self.root,
                environ=self.environment(),
                opener=failing_opener,
                run_git=self.fake_git,
            )

        self.assertNotEqual(exit_code, 0)
        self.assertFalse(output_path.exists())
        self.assertNotIn(API_KEY, stdout.getvalue() + stderr.getvalue())

    def test_missing_key_mismatched_sha_and_invalid_ai_schema_remove_stale_output(self):
        output_path = self.artifact_dir / "openai-review.json"

        for environment, opener, git in (
            ({"EXPECTED_SHA": SHA}, self.completed_opener, self.fake_git),
            ({"EXPECTED_SHA": "b" * 40, "OPENAI_API_KEY": API_KEY}, self.completed_opener, self.fake_git),
            (self.environment(), self.invalid_result_opener, self.fake_git),
        ):
            with self.subTest(environment=environment):
                output_path.write_text("stale", encoding="utf-8")
                self.assertEqual(
                    self.module.main(
                        ["run"], repo_root=self.root, environ=environment, opener=opener, run_git=git
                    ),
                    2,
                )
                self.assertFalse(output_path.exists())

    def invalid_result_opener(self, request, timeout=None):
        payload = {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps({"summary": "unsafe", "findings": [], "extra": True}),
                        }
                    ],
                }
            ],
        }

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *unused):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        return Response()

    def test_incomplete_refused_multiple_or_missing_output_text_are_rejected(self):
        cases = [
            {"status": "incomplete", "output": []},
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "refusal", "refusal": "No."}],
                    }
                ],
            },
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "output_text", "text": "first"},
                            {"type": "output_text", "text": "second"},
                        ],
                    }
                ],
            },
        ]

        for response in cases:
            with self.subTest(response=response):
                self.assertIsNone(self.module.extract_output_text(response))

    def test_mixed_refusal_and_output_text_is_rejected(self):
        response = {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "refusal", "refusal": "No."},
                        {"type": "output_text", "text": json.dumps(valid_ai_object())},
                    ],
                }
            ],
        }

        self.assertIsNone(self.module.extract_output_text(response))

    def test_refusal_in_any_response_message_is_rejected(self):
        response = {
            "status": "completed",
            "output": [
                {
                    "type": "refusal",
                    "refusal": "No.",
                },
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": json.dumps(valid_ai_object())}],
                },
            ],
        }

        self.assertIsNone(self.module.extract_output_text(response))

    def test_artifact_directory_symlink_fails_closed_without_touching_external_output(self):
        external_directory = self.root / "external"
        external_directory.mkdir()
        external_output = external_directory / "openai-review.json"
        external_output.write_text("keep external output", encoding="utf-8")
        (self.artifact_dir / "deterministic.json").unlink()
        self.artifact_dir.rmdir()
        self.make_symlink(self.artifact_dir, external_directory)

        self.assertEqual(
            self.module.main(
                ["run"], repo_root=self.root, environ=self.environment(), opener=self.completed_opener, run_git=self.fake_git
            ),
            2,
        )
        self.assertEqual(external_output.read_text(encoding="utf-8"), "keep external output")

    def test_output_and_legacy_temp_symlinks_fail_closed_without_external_writes(self):
        external_output = self.root / "external-output.json"
        external_output.write_text("keep external output", encoding="utf-8")
        output_path = self.artifact_dir / "openai-review.json"
        self.make_symlink(output_path, external_output)

        self.assertEqual(
            self.module.main(
                ["run"], repo_root=self.root, environ=self.environment(), opener=self.completed_opener, run_git=self.fake_git
            ),
            2,
        )
        self.assertTrue(output_path.is_symlink())
        self.assertEqual(external_output.read_text(encoding="utf-8"), "keep external output")

        output_path.unlink()
        legacy_temp = output_path.with_name(output_path.name + ".tmp")
        self.make_symlink(legacy_temp, external_output)
        self.assertEqual(
            self.module.main(
                ["run"], repo_root=self.root, environ=self.environment(), opener=self.completed_opener, run_git=self.fake_git
            ),
            2,
        )
        self.assertTrue(legacy_temp.is_symlink())
        self.assertEqual(external_output.read_text(encoding="utf-8"), "keep external output")

    def test_request_review_rejects_malformed_response_json(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *unused):
                return False

            def read(self):
                return b"{not json"

        self.assertIsNone(
            self.module.request_review(API_KEY, self.module.build_request("bounded"), opener=lambda *args, **kwargs: Response())
        )


if __name__ == "__main__":
    unittest.main()
