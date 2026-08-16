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
    "slackapi/slack-github-action@dcb1066f776dd043e64d0e8ba94ca15cc7e1875d",
}
EXPECTED_TRIGGER_BLOCK = (
    "on:\n"
    "  schedule:\n"
    "    - cron: \"30 7 * * 1-5\"\n"
    "      timezone: \"Asia/Kolkata\"\n"
    "  workflow_dispatch:\n"
)


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

        trigger_block = re.search(r"(?ms)^on:\n.*?(?=^permissions:)", workflow)
        self.assertIsNotNone(trigger_block)
        self.assertEqual(trigger_block.group(0), EXPECTED_TRIGGER_BLOCK)
        self.assertRegex(workflow, r"(?m)^permissions: \{\}\s*$")
        self.assertIn("group: cordia-daily-production-review-main", workflow)
        self.assertIn("cancel-in-progress: true", workflow)
        expected_guards = {
            "deterministic": "github.ref == 'refs/heads/main'",
            "ai_review": "github.ref == 'refs/heads/main'",
            "slack_notify": "github.ref == 'refs/heads/main'",
            "final_status": "always() && github.ref == 'refs/heads/main'",
        }
        for job_name, guard in expected_guards.items():
            with self.subTest(job_name=job_name):
                self.assertRegex(
                    workflow,
                    rf"(?m)^  {job_name}:\n    if: {re.escape(guard)}$",
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
        self.assertEqual(workflow.count("secrets.OPENAI_API_KEY"), 1)
        self.assertEqual(workflow.count("secrets.SLACK_WEBHOOK_URL"), 1)
        self.assertIn("contents: read", jobs["deterministic"])
        self.assertIn("contents: read", jobs["ai_review"])
        self.assertNotIn("secrets.", jobs["deterministic"])
        self.assertNotIn("secrets.", jobs["final_status"])
        self.assertNotIn("actions/checkout@", jobs["final_status"])
        self.assertNotIn("secrets.", jobs["slack_notify"].replace("secrets.SLACK_WEBHOOK_URL", ""))
        self.assertNotIn("anthropic", workflow.lower())
        self.assertNotIn("claude-code-action", workflow.lower())

        uses_lines = re.findall(r"(?m)^\s*uses:\s+(\S+)\s*$", workflow)
        self.assertTrue(uses_lines)
        self.assertEqual(set(uses_lines), EXPECTED_ACTIONS)
        self.assertEqual(
            len(PINNED_ACTION_PATTERN.findall(workflow)), len(uses_lines)
        )

    def test_openai_adapter_is_report_only_and_isolated_to_its_step(self):
        job = extract_job(self.workflow, "ai_review")

        self.assertRegex(
            job,
            r"(?m)^    env:\n"
            r"      CORDIA_OPENAI_API_KEY: \$\{\{ secrets\.OPENAI_API_KEY \}\}$",
        )
        self.assertIn("if: env.CORDIA_OPENAI_API_KEY != ''", job)
        self.assertIn('python-version: "3.12"', job)
        self.assertIn("fetch-depth: 2", job)
        self.assertRegex(
            job,
            r"(?ms)^      - name: Run the report-only OpenAI review when configured\n"
            r"        id: openai\n"
            r"        if: env\.CORDIA_OPENAI_API_KEY != ''\n"
            r"        continue-on-error: true\n"
            r"        env:\n"
            r"          OPENAI_API_KEY: \$\{\{ env\.CORDIA_OPENAI_API_KEY \}\}\n"
            r"          EXPECTED_SHA: \$\{\{ github\.sha \}\}\n"
            r"        run: python tools/openai_production_review\.py run$",
        )
        self.assertIn("AI_REVIEW_PATH: .production-review/openai-review.json", job)
        self.assertIn("MODEL_REVIEW_CONFIGURED: ${{ steps.openai.outcome != 'skipped' && 'true' || 'false' }}", job)
        steps = {
            match.group("name"): match.group(0)
            for match in re.finditer(
                r"(?ms)^      - name: (?P<name>[^\n]+)\n.*?(?=^      - name:|\Z)",
                job,
            )
        }
        self.assertEqual(
            set(steps),
            {
                "Check out the same reviewed commit",
                "Set up Python",
                "Download the bounded deterministic result",
                "Run the report-only OpenAI review when configured",
                "Assemble bounded review artifacts without integration secrets",
                "Add the validated review to the run summary",
                "Retain the bounded final review",
            },
        )
        adapter_name = "Run the report-only OpenAI review when configured"
        for step_name, step in steps.items():
            with self.subTest(step_name=step_name):
                if step_name == adapter_name:
                    self.assertRegex(step, r"(?m)^          OPENAI_API_KEY: ")
                    self.assertRegex(step, r"(?m)^          EXPECTED_SHA: ")
                else:
                    self.assertRegex(
                        step,
                        r"(?m)^          CORDIA_OPENAI_API_KEY: \"\"$",
                    )
                    self.assertNotRegex(step, r"(?m)^          OPENAI_API_KEY: ")
        for forbidden in ("/cordia-production-review", "Bash", "Write", "Edit", "github_token"):
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
