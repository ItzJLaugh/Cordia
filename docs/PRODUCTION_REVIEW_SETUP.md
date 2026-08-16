# Production-review setup

An administrator adds the two repository secrets in GitHub: `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`.

- `ANTHROPIC_API_KEY`
- `SLACK_WEBHOOK_URL`

Never paste secret values into chat, repository files, issues, pull requests, logs, or Slack. If either secret is absent, the review is setup-required: record that condition and choose `Blocked`; do not invent a value or bypass the check.

For the first manual run, start from current `main`, verify the commit SHA, and use the production-review workflow. A configured review only reports evidence; it does not authorize deployment, merge, direct-main edits, secret access, or Hostinger access.
