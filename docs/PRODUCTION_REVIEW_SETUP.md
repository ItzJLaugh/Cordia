# Production-review setup

An administrator adds the two repository secrets in GitHub: `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`.

- `ANTHROPIC_API_KEY`
- `SLACK_WEBHOOK_URL`

Never paste secret values into chat, repository files, issues, pull requests, logs, or Slack. If the Anthropic secret is absent, the review reports its existing setup-required state and no AI request is made. If the Slack webhook is absent, the `slack_notify` job records the separate bounded status `SETUP REQUIRED`, retains it as `cordia-slack-notification-status`, and sends no Slack request. A configured delivery records `NOTIFICATION SENT` or `NOTIFICATION FAILED` without exposing the webhook or response body. Record a missing integration as `Blocked`; do not invent a value or bypass the check.

For the first manual run, start from current `main`, verify the commit SHA, and use the production-review workflow. A configured review only reports evidence; it does not authorize deployment, merge, direct-main edits, secret access, or Hostinger access.
