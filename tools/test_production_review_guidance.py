"""Structural checks for the human production-review guidance."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProductionReviewGuidanceTests(unittest.TestCase):
    def read_target(self, relative_path: str) -> str:
        path = ROOT / relative_path
        self.assertTrue(path.is_file(), f"Missing required guidance file: {relative_path}")
        return path.read_text(encoding="utf-8")

    def test_required_guidance_files_exist(self) -> None:
        for relative_path in (
            "CLAUDE.md",
            ".claude/skills/cordia-production-review/SKILL.md",
            "docs/PRODUCTION_REVIEW_PLAYBOOK.md",
            "docs/PRODUCTION_REVIEW_SETUP.md",
            "docs/superpowers/plans/2026-08-15-cordia-daily-production-review.md",
            ".github/pull_request_template.md",
            ".github/ISSUE_TEMPLATE/production-review-finding.yml",
            ".github/ISSUE_TEMPLATE/production-review-record.yml",
            "tools/test_production_review_guidance.py",
        ):
            with self.subTest(relative_path=relative_path):
                self.read_target(relative_path)

    def test_required_human_review_guidance(self) -> None:
        skill = self.read_target(".claude/skills/cordia-production-review/SKILL.md")
        playbook = self.read_target("docs/PRODUCTION_REVIEW_PLAYBOOK.md")
        setup = self.read_target("docs/PRODUCTION_REVIEW_SETUP.md")
        pr_template = self.read_target(".github/pull_request_template.md")
        issue_form = self.read_target(".github/ISSUE_TEMPLATE/production-review-finding.yml")
        record_form = self.read_target(".github/ISSUE_TEMPLATE/production-review-record.yml")

        self.assertIn("name: cordia-production-review", skill)
        self.assertIn("review/YYYY-MM-DD-<short-topic>", skill)
        self.assertIn("Never edit directly on `main`", skill)
        self.assertIn("python tools/production_review.py run", skill)
        for outcome in ("Reviewed clean", "Fix PR opened", "Follow-up issue opened", "Blocked"):
            self.assertIn(outcome, skill)
        self.assertIn("7:30 AM India time", playbook)
        self.assertIn("OPENAI_API_KEY", setup)
        self.assertIn("SLACK_WEBHOOK_URL", setup)
        self.assertIn("gpt-5.4-mini-2026-03-17", setup)
        self.assertIn("official GitHub Slack app", setup)
        self.assertIn("optional", setup.lower())
        self.assertIn("required for the scheduled AI advisory", setup)
        self.assertIn("does not block", setup)
        self.assertNotIn("ANTHROPIC_API_KEY", setup)
        spec = self.read_target("docs/superpowers/specs/2026-08-15-cordia-daily-production-review-design.md")
        self.assertNotIn("ANTHROPIC_API_KEY", spec)
        self.assertNotIn("both GitHub secrets", spec)
        self.assertIn("only `OPENAI_API_KEY` is required", spec)
        self.assertIn("does not block the review", spec)
        self.assertIn("fixed OpenAI adapter instructions", spec)
        self.assertIn("`CLAUDE.md` is untrusted scheduled input", spec)
        self.assertNotIn("sk-ant-", setup)
        self.assertNotIn("xoxb-", setup)
        self.assertIn("This review does not authorize deployment", pr_template)
        self.assertIn("Human validation", issue_form)
        self.assertIn("Daily production-review record", record_form)

        for guidance in (playbook, skill):
            with self.subTest(guidance=guidance[:40]):
                self.assertIn("official GitHub Slack app", guidance)
                self.assertIn("native workflow notification", guidance)
                self.assertIn("without `SLACK_WEBHOOK_URL`", guidance)
                self.assertIn("custom Cordia Block Kit", guidance)
                self.assertIn("optional", guidance.lower())
                self.assertIn("Open full review", guidance)

        historical_plan = self.read_target(
            "docs/superpowers/plans/2026-08-15-cordia-daily-production-review.md"
        )
        self.assertIn("Status: Historical and superseded", historical_plan)
        self.assertIn(
            "docs/superpowers/plans/2026-08-16-openai-production-review.md",
            historical_plan,
        )
        self.assertIn("only `OPENAI_API_KEY` is required", historical_plan)
        self.assertIn("`SLACK_WEBHOOK_URL` is optional", historical_plan)
        self.assertNotIn(
            "ask Jackson to add `ANTHROPIC_API_KEY` and `SLACK_WEBHOOK_URL`",
            historical_plan,
        )

    def test_fixed_runner_guidance_supplies_sha_and_readiness_commands(self) -> None:
        skill = self.read_target(".claude/skills/cordia-production-review/SKILL.md")

        for required_command in (
            "python --version",
            "node --version",
            "npm.cmd --version",
            "python -m pip install --requirement backend/requirements.txt",
            "$env:EXPECTED_SHA = $reviewedSha",
            "python tools/production_review.py run",
            "python3 --version",
            "npm --version",
            "python3 -m pip install --requirement backend/requirements.txt",
            'EXPECTED_SHA="$reviewed_sha" python3 tools/production_review.py run',
        ):
            with self.subTest(required_command=required_command):
                self.assertIn(required_command, skill)

    def test_issue_forms_use_exact_taxonomies_and_record_every_outcome(self) -> None:
        finding_form = self.read_target(
            ".github/ISSUE_TEMPLATE/production-review-finding.yml"
        )
        record_form = self.read_target(
            ".github/ISSUE_TEMPLATE/production-review-record.yml"
        )
        skill = self.read_target(".claude/skills/cordia-production-review/SKILL.md")
        playbook = self.read_target("docs/PRODUCTION_REVIEW_PLAYBOOK.md")

        self.assertEqual(
            self.dropdown_options(finding_form, "severity"),
            ["Critical", "Important", "Minor"],
        )
        self.assertEqual(
            self.dropdown_options(record_form, "outcome"),
            [
                "Reviewed clean",
                "Fix PR opened",
                "Follow-up issue opened",
                "Blocked",
            ],
        )
        for required_id in ("reviewed_sha", "review_run", "outcome", "human_record"):
            with self.subTest(required_id=required_id):
                self.assertRegex(record_form, rf"(?m)^    id: {required_id}$")
        self.assertIn("GitHub Issues", skill)
        self.assertIn("Daily production-review record", skill)
        self.assertIn("Daily production-review record", playbook)
        self.assertIn("Every daily review", playbook)

    @staticmethod
    def dropdown_options(form: str, dropdown_id: str) -> list[str]:
        dropdown = re.search(
            rf"(?ms)^  - type: dropdown\n    id: {re.escape(dropdown_id)}\n"
            rf"(?P<body>.*?)(?=^  - type:|\Z)",
            form,
        )
        if dropdown is None:
            raise AssertionError(f"Missing dropdown {dropdown_id!r}")
        options = re.search(
            r"(?ms)^      options:\n(?P<options>(?:        - [^\n]+\n)+)",
            dropdown.group("body"),
        )
        if options is None:
            raise AssertionError(f"Missing options for dropdown {dropdown_id!r}")
        return re.findall(r"(?m)^        - (.+)$", options.group("options"))


if __name__ == "__main__":
    unittest.main()
