# Production-review setup

An administrator adds the OpenAI repository secret in GitHub: `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`.

- `OPENAI_API_KEY` is required for the scheduled AI advisory and uses the pinned OpenAI Responses API model `gpt-5.4-mini-2026-03-17`.

Never paste secret values into chat, repository files, issues, pull requests, logs, or Slack. If the required OpenAI secret is absent, no AI request is made and the review reports `REVIEW UNAVAILABLE`; a human may record the required configuration gap as `Blocked`. The official GitHub Slack app may provide native workflow notifications without any webhook. `SLACK_WEBHOOK_URL` is optional only when the team wants the custom Cordia Block Kit summary: if it is absent, the `slack_notify` job records the separate bounded status `SETUP REQUIRED`, retains it as `cordia-slack-notification-status`, and sends no custom Slack request. The missing optional webhook does not block the review and must not be recorded as `Blocked`. A configured custom delivery records `NOTIFICATION SENT` or `NOTIFICATION FAILED` without exposing the webhook or response body.

For the first manual run, start from current `main`, verify the commit SHA, and use the production-review workflow. A configured review only reports evidence; it does not authorize deployment, merge, direct-main edits, secret access, or Hostinger access.
