"""Structural checks for the human production-review guidance."""

from pathlib import Path
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
            ".github/pull_request_template.md",
            ".github/ISSUE_TEMPLATE/production-review-finding.yml",
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

        self.assertIn("name: cordia-production-review", skill)
        self.assertIn("review/YYYY-MM-DD-<short-topic>", skill)
        self.assertIn("Never edit directly on `main`", skill)
        self.assertIn("python tools/production_review.py run", skill)
        for outcome in ("Reviewed clean", "Fix PR opened", "Follow-up issue opened", "Blocked"):
            self.assertIn(outcome, skill)
        self.assertIn("7:30 AM India time", playbook)
        self.assertIn("ANTHROPIC_API_KEY", setup)
        self.assertIn("SLACK_WEBHOOK_URL", setup)
        self.assertNotIn("sk-ant-", setup)
        self.assertNotIn("xoxb-", setup)
        self.assertIn("This review does not authorize deployment", pr_template)
        self.assertIn("Human validation", issue_form)


if __name__ == "__main__":
    unittest.main()
