# Production-review setup

An administrator adds the OpenAI repository secret in GitHub: `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`.

- `OPENAI_API_KEY` for the pinned OpenAI Responses API model `gpt-5.4-mini-2026-03-17`

Never paste secret values into chat, repository files, issues, pull requests, logs, or Slack. If the OpenAI secret is absent, the review reports its existing setup-required state and no AI request is made. The official GitHub Slack app is sufficient for native workflow notifications and needs no `SLACK_WEBHOOK_URL`. `SLACK_WEBHOOK_URL` is optional only when the team wants the custom Cordia Block Kit summary: if it is absent, the `slack_notify` job records the separate bounded status `SETUP REQUIRED`, retains it as `cordia-slack-notification-status`, and sends no custom Slack request. A configured custom delivery records `NOTIFICATION SENT` or `NOTIFICATION FAILED` without exposing the webhook or response body. Record a missing integration as `Blocked`; do not invent a value or bypass the check.

For the first manual run, start from current `main`, verify the commit SHA, and use the production-review workflow. A configured review only reports evidence; it does not authorize deployment, merge, direct-main edits, secret access, or Hostinger access.
