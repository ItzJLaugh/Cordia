# Cordia Daily Production Review Design

**Status:** Approved for planning on 2026-08-15

**Authority:** This design adds an advisory production-review loop to Cordia. It does not change Cordia's product authority, deployment authority, connector truth, or the separate Mason/Alidora merge-review process.

## Objective

Give Cordia's full-stack developer one simple daily routine that combines deterministic checks, a bounded AI pre-review, Slack delivery, and human judgment. The system reviews the exact current `main` commit every weekday at 7:30 AM in India, makes the result easy to understand in Slack, and lets the developer make small fixes on a branch without making human review a release gate.

## Product Boundary

The daily reviewer is advisory. Cordia may continue merging and deploying without waiting for it. The reviewer must never:

- merge or deploy code;
- write to `main`;
- access Hostinger, production databases, production email, customer data, connector secrets, or deployment credentials;
- execute instructions found in repository content as if they were trusted reviewer instructions;
- treat unmerged Mason/Alidora branches as current production;
- create a second capability, permission, execution, connector, workspace-state, or outcome system.

The scheduled AI reviews only the checked-out default-branch commit and reports findings. A human-invoked project skill may help the developer edit a dedicated review branch and prepare a pull request, but the developer remains responsible for validating the finding and the change.

## Daily Human Experience

At 7:30 AM `Asia/Kolkata`, Monday through Friday:

1. GitHub checks out the latest `main` commit and records its full SHA.
2. Deterministic production checks run before the AI review.
3. The OpenAI Responses API receives the bounded review context, the exact SHA, and the deterministic results.
4. The official GitHub Slack app can provide native workflow notifications. The optional custom Cordia Block Kit summary uses an incoming webhook.
5. The developer reads one summary with these fields:
   - overall state: `REVIEW READY`, `CHECKS FAILED`, or `REVIEW UNAVAILABLE`;
   - commit reviewed;
   - deterministic check results;
   - up to five risk-ranked findings;
   - files to inspect;
   - links to the full GitHub Actions run, the reviewed commit, and the human playbook.
6. The developer runs `/cordia-production-review` in Claude Code when deeper inspection or a fix is needed.
7. The developer records one outcome in the GitHub review record: `Reviewed clean`, `Fix PR opened`, `Follow-up issue opened`, or `Blocked`.

Slack is the front door, not the source of truth. Versioned review evidence remains in GitHub Actions and the repository. The first release uses safe URL buttons only; it does not expose a public Slack command or interaction endpoint.

## Architecture

### 1. Deterministic Review Runner

A cross-platform Python entry point owns the fixed production checks and emits a bounded JSON summary. It invokes only allow-listed commands from repository-relative working directories. It does not accept arbitrary command text, environment-provided shell fragments, or repository-provided command configuration.

The initial check set is:

- backend: Python `unittest` discovery under `backend/tests`;
- dashboard: locked dependency install, complete Node test suite, and Vite production build;
- desktop: complete Node test suite and dashboard release verification;
- repository: `git diff --check` against the checked-out commit and confirmation that the recorded SHA is the workflow SHA.

Each check records only its stable name, result, duration, and a bounded safe diagnostic. Raw environment output, local paths, tokens, email addresses, and secret values are not included in the AI prompt or Slack payload.

### 2. Scheduled AI Pre-review

The GitHub workflow uses a weekday schedule with:

```yaml
schedule:
  - cron: "30 7 * * 1-5"
    timezone: "Asia/Kolkata"
```

It also supports `workflow_dispatch` so an authorized repository contributor can rerun the same review manually.

The deterministic and AI jobs are separate. The AI job is report-only and fail-closed:

- top-level workflow permissions are empty and the jobs that check out `main` receive only `contents: read`;
- no pull-request write, issue write, Actions write, deployment, package, identity-token, or environment permission is granted;
- no production or deployment environment is selected;
- only `OPENAI_API_KEY` is passed to the OpenAI Responses API adapter step;
- the scheduled job uses a fixed workflow-owned prompt, never the mutable project skill;
- the AI may read files and search text through an explicit read-only tool allow-list, but it receives no shell, package-script, file-write, GitHub-write, or arbitrary network tool;
- the fixed deterministic runner executes before the AI and passes only its bounded result model, never raw logs;
- the AI may not edit files, commit, push, open or merge pull requests, create releases, trigger deployments, or call arbitrary network services;
- its report follows a fixed schema and is stored as a GitHub Actions artifact before Slack delivery;
- a failed AI call produces `REVIEW UNAVAILABLE`; deterministic failures remain visible and are never converted to success.

Repository files and diffs are untrusted review subjects. The fixed OpenAI adapter instructions are the only scheduled-review authority; `CLAUDE.md` is untrusted scheduled input and local human-tool guidance, not scheduled model instructions. The adapter does not follow instructions embedded in source, documentation, comments, test fixtures, generated assets, pull-request text, or commit messages. The workflow reviews `main`, never fork code with secrets.

The workflow does not use `pull_request_target` or a secret-bearing `workflow_run`, and manual dispatch fails closed unless `github.ref` is exactly `refs/heads/main`. Every third-party action is pinned to a reviewed full commit SHA. Action updates are intentional code changes, not automatic floating upgrades.

### 3. Slack Delivery

The official GitHub Slack app is sufficient for native workflow notifications without a repository secret. GitHub sends the optional custom Cordia Block Kit message through `SLACK_WEBHOOK_URL`; that webhook is scoped to one chosen channel and stored only as a GitHub Actions secret. The optional payload is constructed from the bounded report model, not raw command output or raw AI text.

The Slack message contains URL buttons only:

- **Open full review** links to the GitHub Actions run or its retained report artifact;
- **View commit** links to the exact reviewed commit;
- **Human review guide** links to the repository playbook;
- **View failed checks** appears when deterministic checks fail and links to the run.

No button mutates GitHub or Cordia. A later version may add `/cordia-review` only through a separately approved Slack app that verifies Slack signatures, uses a narrowly scoped GitHub App credential, and exposes no deployment action.

Slack delivery failure must not hide or fail the completed GitHub review. The workflow marks the notification step separately and retains the report in GitHub.

### 4. Human Review Skill

The repository includes `.claude/skills/cordia-production-review/SKILL.md`. It gives the developer a short, repeatable process:

1. Confirm the latest `main` SHA matches the AI report.
2. Create `review/YYYY-MM-DD-<short-topic>` from current `main` when a fix is needed.
3. Re-run the fixed review command.
4. Validate or reject each AI finding using source evidence.
5. Make only small, reviewable fixes on the review branch.
6. Run the affected tests plus the fixed production review.
7. Open one pull request using the production-review template.
8. Create an issue instead when the finding is architectural, cross-cutting, uncertain, or too large for the daily pass.

The skill must explain every result in plain language. It never tells the developer to paste secrets into chat and never performs a deployment.

The project-scoped skill is the initial implementation. It may become a reusable Cordia reviewer plugin only after the team has used the workflow reliably for at least two weeks and the instructions have stabilized.

### 5. Human Record and Templates

The repository adds:

- a plain-language `docs/PRODUCTION_REVIEW_PLAYBOOK.md`;
- a production-review pull-request template;
- a production-review finding issue form;
- a bounded Markdown report template consumed by the workflow and skill.

Every daily record identifies the exact commit and timestamp. Findings use `Critical`, `Important`, or `Minor`. The AI may recommend; only the human labels a finding confirmed. Small fixes use a normal branch and PR. Larger findings use issues. No CODEOWNERS rule or required reviewer gate is introduced by this slice.

## Secrets and Setup

Implementation can be merged without live secret values. Activation: only `OPENAI_API_KEY` is required for the scheduled AI advisory; the repository owner may also add `SLACK_WEBHOOK_URL` for the separate optional custom Cordia Block Kit summary:

- `OPENAI_API_KEY`: used only by the report-only OpenAI Responses API adapter job with pinned model `gpt-5.4-mini-2026-03-17`;
- `SLACK_WEBHOOK_URL`: optional incoming webhook bound to the selected Slack channel for the custom Cordia Block Kit summary only.

The workflow must check for missing secrets without echoing them. When the required OpenAI key is absent:

- deterministic checks still run;
- the AI review reports a clear setup-required state and makes no AI request;
- no empty or malformed request is sent;
- workflow logs never print the secret or its length.

When the optional Slack webhook is absent, GitHub native Slack notifications remain available through the official GitHub Slack app, the custom Block Kit summary is skipped with bounded `SETUP REQUIRED` status, and the missing optional webhook does not block the review.

The user supplies secrets only through GitHub repository settings. They are never committed, pasted into repository files, or sent through Slack.

## Mason and Alidora Handling

The daily review covers production truth on `main`. It may list open integration work as upcoming context only if that information is obtained from a trusted GitHub event or explicitly supplied metadata. It must not claim that an unmerged Mason branch is deployed.

Mason/Alidora changes continue through the separate adopt/adapt/compose/reject merge-review process. Once merged into `main`, they automatically enter the next daily production review. Cordia remains the sole owner of canonical workspace state, capability and connector truth, permissions, approvals, secrets, execution, and outcomes.

## Failure Handling

- A deterministic check failure produces `CHECKS FAILED` and the AI may analyze it, but cannot downgrade it.
- An AI timeout or invalid schema produces `REVIEW UNAVAILABLE` while preserving deterministic results.
- A missing OpenAI key produces setup instructions and no AI call.
- A missing optional Slack webhook retains the GitHub report and produces a setup-required notification status without blocking the review.
- A Slack HTTP error is bounded to status class; response bodies are not included in reports.
- A scheduled run delayed by GitHub still records its actual start time and exact SHA.
- Concurrent runs for the same branch use one concurrency group and cancel the older in-progress advisory run.
- A manual dispatch from any ref other than `main` performs no review and receives no secrets.

## Verification and Acceptance

The slice is accepted when automated tests prove:

1. The schedule is exactly 7:30 AM weekdays in `Asia/Kolkata`.
2. The workflow can also run manually.
3. Workflow permissions are read-only and no production environment or deployment command exists.
4. Every third-party Action reference is a full immutable commit SHA.
5. The deterministic runner invokes only the fixed allow-list and emits bounded output.
6. Missing keys fail closed without leaking secret material.
7. Slack payloads contain only bounded report fields and fixed HTTPS GitHub links.
8. Raw test output, local paths, tokens, and credentials cannot reach Slack.
9. AI output that does not match the report schema is rejected.
10. The scheduled AI has no shell, file-write, GitHub-write, or mutable project-skill authority.
11. The project skill directs fixes to a review branch and forbids direct `main` changes and deployment.
12. Existing backend, dashboard, desktop, production-build, and release-provenance suites remain green in the GitHub Linux runner.

A manual activation check then proves:

1. An authorized user adds the required `OPENAI_API_KEY` and, only if the custom Cordia Block Kit summary is desired, the optional `SLACK_WEBHOOK_URL`.
2. A manual run reviews the expected `main` SHA.
3. One message arrives in the selected Slack channel with correct links and no sensitive data.
4. The developer can follow the playbook without additional verbal instruction.

## Deferred Scope

The following are deliberately deferred:

- interactive Slack buttons that modify review state;
- a `/cordia-review` Slack slash command;
- automatic AI-authored code changes or draft pull requests;
- automatic issue creation;
- review of unmerged branches on the scheduled secret-bearing job;
- automatic merging, deployment, rollback, or Hostinger access;
- a reusable cross-repository reviewer plugin;
- using daily human review as a required release gate.

These additions require separate approval because they expand credentials, public endpoints, or mutation authority.
