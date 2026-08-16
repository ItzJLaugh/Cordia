Open `#cordia-production-review` at 7:30 AM India time. Click `Open full review`. Verify the report SHA against current `main`. Run `/cordia-production-review`. Validate every finding in the source. Choose one outcome.

# Daily production-review playbook

1. If the SHA differs, choose `Blocked` and request a fresh review.
2. If the report is clean or no finding is confirmed, choose `Reviewed clean`.
3. For one small, confirmed fix: create a review branch, make the limited repair, run affected and full checks, then choose `Fix PR opened`.
4. For a large, unclear, or cross-cutting finding: open the follow-up issue with evidence and choose `Follow-up issue opened`.

Do not treat an AI report as proof. Do not reveal secrets or deploy, merge, edit `main` directly, or access Hostinger. A review ends with exactly one named outcome.
