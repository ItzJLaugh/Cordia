Open `#cordia-production-review` at 7:30 AM India time. The official GitHub Slack app route uses a native workflow notification without `SLACK_WEBHOOK_URL`; open that notification's GitHub Actions run and navigate to the retained production-review artifact. The optional custom Cordia Block Kit route uses `SLACK_WEBHOOK_URL`; click `Open full review`. From either route, verify the report SHA against current `main`, run `/cordia-production-review`, validate every finding in the source, and record one outcome.

# Daily production-review playbook

1. If the SHA differs, choose `Blocked` and request a fresh review.
2. If the report is clean or no finding is confirmed, choose `Reviewed clean`.
3. For one small, confirmed fix: create a review branch, make the limited repair, run affected and full checks, then choose `Fix PR opened`.
4. For a large, unclear, or cross-cutting finding: open the follow-up issue with evidence and choose `Follow-up issue opened`.
5. In GitHub Issues, choose `New issue` -> `Daily production-review record`. Enter the reviewed SHA and Actions run, select the one outcome, and link any PR or follow-up issue. Every daily review must have exactly one durable record; issue creation is a human action, never workflow automation.

Do not treat an AI report as proof. Do not reveal secrets or deploy, merge, edit `main` directly, or access Hostinger. A review ends only after its one named outcome is recorded.
