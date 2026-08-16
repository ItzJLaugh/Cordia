from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "daily-production-review.yml"
PINNED_ACTION_PATTERN = re.compile(
    r"^\s*uses:\s+[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}\s*$",
    re.MULTILINE,
)
EXPECTED_ACTIONS = {
    "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
    "actions/setup-python@42375524e23c412d93fb67b49958b491fce71c38",
    "actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020",
    "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
    "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
    "anthropics/claude-code-action@c3d45e8e941e1b2ad7b278c57482d9c5bf1f35b3",
    "slackapi/slack-github-action@dcb1066f776dd043e64d0e8ba94ca15cc7e1875d",
}


def extract_job(workflow, job_name):
    match = re.search(
        rf"^  {re.escape(job_name)}:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        workflow,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"workflow job {job_name!r} is missing")
    return match.group(0)


class DailyProductionReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_schedule_manual_trigger_and_fail_closed_workflow_boundary(self):
        workflow = self.workflow

        self.assertIn('cron: "30 7 * * 1-5"', workflow)
        self.assertIn('timezone: "Asia/Kolkata"', workflow)
        self.assertRegex(workflow, r"(?m)^  workflow_dispatch:\s*$")
        self.assertRegex(workflow, r"(?m)^permissions: \{\}\s*$")
        self.assertIn("group: cordia-daily-production-review-main", workflow)
        self.assertIn("cancel-in-progress: true", workflow)
        self.assertGreaterEqual(
            workflow.count("if: github.ref == 'refs/heads/main'"), 3
        )

        lowered = workflow.lower()
        for forbidden in (
            "pull_request_target",
            "workflow_run",
            "repository_dispatch",
            "environment:",
            "hostinger",
            "ssh",
            "scp",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered)
        self.assertIsNone(
            re.search(r"(?m)^\s+[a-z][a-z-]*:\s*write\s*$", lowered)
        )

    def test_jobs_actions_permissions_and_secret_references_are_exact(self):
        workflow = self.workflow

        jobs = {
            name: extract_job(workflow, name)
            for name in ("deterministic", "ai_review", "slack_notify", "final_status")
        }
        self.assertEqual(workflow.count("secrets.ANTHROPIC_API_KEY"), 1)
        self.assertEqual(workflow.count("secrets.SLACK_WEBHOOK_URL"), 1)
        self.assertIn("contents: read", jobs["deterministic"])
        self.assertIn("contents: read", jobs["ai_review"])
        self.assertNotIn("secrets.", jobs["deterministic"])
        self.assertNotIn("secrets.", jobs["final_status"])
        self.assertNotIn("actions/checkout@", jobs["final_status"])

        uses_lines = re.findall(r"(?m)^\s*uses:\s+(\S+)\s*$", workflow)
        self.assertTrue(uses_lines)
        self.assertEqual(set(uses_lines), EXPECTED_ACTIONS)
        self.assertEqual(
            len(PINNED_ACTION_PATTERN.findall(workflow)), len(uses_lines)
        )

    def test_claude_is_report_only_with_bare_read_search_access(self):
        job = extract_job(self.workflow, "ai_review")

        self.assertRegex(
            job,
            r"(?m)^    env:\n"
            r"      CORDIA_ANTHROPIC_API_KEY: \$\{\{ secrets\.ANTHROPIC_API_KEY \}\}$",
        )
        self.assertIn("if: env.CORDIA_ANTHROPIC_API_KEY != ''", job)
        self.assertGreaterEqual(
            job.count('CORDIA_ANTHROPIC_API_KEY: ""'), 5
        )
        self.assertIn("github_token: ${{ github.token }}", job)
        self.assertIn('show_full_output: "false"', job)
        self.assertIn('display_report: "false"', job)
        self.assertIn("--bare", job)
        self.assertIn("CLAUDE_CODE_DISABLE_AUTO_MEMORY", job)
        self.assertIn("CLAUDE_CODE_DISABLE_BACKGROUND_TASKS", job)
        self.assertIn("CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS", job)
        self.assertIn("--disable-slash-commands", job)
        self.assertIn('--setting-sources ""', job)
        self.assertIn('--tools "Read,Grep,Glob"', job)
        self.assertIn("--max-turns 4", job)
        self.assertIn("--json-schema", job)
        self.assertIn("untrusted", job.lower())
        for forbidden in ("/cordia-production-review", "Bash", "Write", "Edit"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, job)

    def test_slack_receives_only_the_validated_payload_artifact(self):
        job = extract_job(self.workflow, "slack_notify")

        self.assertRegex(
            job,
            r"(?m)^    env:\n"
            r"      CORDIA_SLACK_WEBHOOK_URL: \$\{\{ secrets\.SLACK_WEBHOOK_URL \}\}$",
        )
        self.assertIn("if: env.CORDIA_SLACK_WEBHOOK_URL != ''", job)
        self.assertIn("id: slack_delivery", job)
        self.assertIn('CORDIA_SLACK_WEBHOOK_URL: ""', job)
        self.assertIn(".production-review/slack.json", job)
        self.assertIn("webhook-type: incoming-webhook", job)
        self.assertNotIn("actions/checkout@", job)
        self.assertNotIn("tools/", job)
        self.assertNotRegex(job, r"(?mi)^\s*run:\s*(?:python|node|npm|git)\b")

    def test_slack_job_records_one_bounded_notification_status_without_repository_code(self):
        job = extract_job(self.workflow, "slack_notify")

        expected_statuses = {
            "SETUP REQUIRED": "true",
            "NOTIFICATION SENT": "false",
            "NOTIFICATION FAILED": "false",
        }
        for status, setup_required in expected_statuses.items():
            with self.subTest(status=status):
                self.assertIn(
                    f'{{"status":"{status}","setup_required":{setup_required}}}',
                    job,
                )
        for outcome in ("skipped", "success", "failure"):
            with self.subTest(outcome=outcome):
                self.assertIn(
                    f"steps.slack_delivery.outcome == '{outcome}'",
                    job,
                )
        self.assertIn("name: cordia-slack-notification-status", job)
        self.assertIn(".production-review/slack-notification.json", job)
        self.assertEqual(self.workflow.count("secrets.SLACK_WEBHOOK_URL"), 1)
        for forbidden in ("actions/checkout@", "tools/", "python ", "node ", "npm ", "git "):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, job)

    def test_final_status_depends_on_review_and_notification_and_only_checks_fail(self):
        job = extract_job(self.workflow, "final_status")

        self.assertRegex(
            job,
            r"(?m)^    needs:\n      - ai_review\n      - slack_notify$",
        )
        self.assertIn("name: cordia-slack-notification-status", job)
        self.assertIn(".production-review/slack-notification.json", job)
        self.assertIn('review_state = "REVIEW UNAVAILABLE"', job)
        self.assertIn('slack_status = "NOTIFICATION UNAVAILABLE"', job)
        self.assertIn("if [ \"$review_state\" = \"CHECKS FAILED\" ]; then", job)
        self.assertEqual(job.count("exit 1"), 1)
        self.assertNotRegex(job, r"REVIEW UNAVAILABLE[^\n]*exit")
        self.assertNotIn("exit 2", job)


if __name__ == "__main__":
    unittest.main()
