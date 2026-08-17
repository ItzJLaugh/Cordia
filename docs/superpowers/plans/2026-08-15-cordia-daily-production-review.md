# Cordia Daily Production Review Implementation Plan

> **Status: Historical and superseded. Do not execute this plan.** The active implementation plan is `docs/superpowers/plans/2026-08-16-openai-production-review.md`. Current activation uses the OpenAI adapter: only `OPENAI_API_KEY` is required for the scheduled advisory, and `SLACK_WEBHOOK_URL` is optional for the custom Cordia Block Kit route. Anthropic and mandatory-webhook instructions below are retained only as historical design evidence.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a weekday 7:30 AM India-time, report-only Cordia production review with deterministic checks, a bounded Claude assessment, a simple Slack notification, and a human-guided small-fix skill.

**Architecture:** A fixed Python runner executes allow-listed checks without secrets. Separate GitHub jobs isolate repository test execution, Claude's key, and Slack's webhook. Claude receives a fixed prompt, structured output, read-only tools, disabled project instructions/skills, and no shell. Slack receives only validated fields and fixed GitHub links. The human skill runs separately in the developer's session.

**Tech Stack:** Python 3.12 standard library and `unittest`; GitHub Actions; Claude Code GitHub Action; Slack incoming webhook; Markdown and YAML.

**Spec:** `docs/superpowers/specs/2026-08-15-cordia-daily-production-review-design.md`

## Global Constraints

- Use exactly `cron: "30 7 * * 1-5"` and `timezone: "Asia/Kolkata"`.
- Run secret-bearing jobs only for `refs/heads/main`.
- Use top-level `permissions: {}` and at most `contents: read` on source-reading jobs.
- Run repository tests without Anthropic, Slack, production, deployment, or GitHub-write credentials.
- Give Claude no shell, write tool, mutable project skill, project memory, or auto-memory.
- Let the Slack job receive only `SLACK_WEBHOOK_URL`; it must not check out or run repository code.
- Never send raw command output or raw Claude execution output to Slack.
- Allow at most five findings using only `Critical`, `Important`, or `Minor`.
- Pin every third-party Action to the exact 40-character SHA in Task 4.
- Never merge, deploy, edit `main`, open issues/PRs, call Hostinger, or run arbitrary PR-head code from the scheduled workflow.
- Human fixes use `review/YYYY-MM-DD-<short-topic>` and remain advisory.
- Preserve Cordia as the only product-state, connector-truth, permission, approval, secret, execution, and outcome owner.

---

### Task 1: Deterministic production-review runner

**Files:**
- Create: `tools/production_review.py`
- Create: `tools/test_production_review.py`
- Modify: `.gitignore`

**Interfaces:**
- `CheckSpec(check_id: str, cwd: str, argv: tuple[str, ...], timeout_seconds: int)`.
- `check_specs(platform=None, python=None) -> tuple[CheckSpec, ...]`.
- `run_review(repo_root, *, expected_sha, executor, now, platform=None, python=None) -> dict`.
- CLI `python tools/production_review.py run` writes `.production-review/deterministic.json` and private bounded logs.

- [ ] **Step 1: Write a failing registry test**

Create `tools/test_production_review.py` and dynamically import the missing module. Assert this exact registry:

```python
self.assertEqual([x.check_id for x in review.check_specs(platform="linux", python="python3")], [
    "backend-tests", "dashboard-install", "dashboard-tests", "dashboard-build",
    "desktop-install", "desktop-tests", "dashboard-release", "commit-diff-check",
])
self.assertEqual(review.check_specs(platform="linux", python="python3")[0].argv,
    ("python3", "-m", "unittest", "discover", "-s", "tests", "-v"))
self.assertEqual(review.check_specs(platform="linux", python="python3")[-1].argv,
    ("git", "diff", "--check", "HEAD^", "HEAD"))
```

- [ ] **Step 2: Confirm RED**

Run `C:\Users\jacks\AppData\Local\Programs\Python\Python312\python.exe -m unittest tools/test_production_review.py -v`.

Expected: missing `tools/production_review.py`.

- [ ] **Step 3: Implement the immutable registry**

Use a frozen dataclass. Resolve `npm.cmd` only when `platform == "nt"`; otherwise use `npm`. Fixed working directories are `.`, `backend`, `dashboard-app`, and `desktop`. Every call uses an argv list, `shell=False`, `check=False`, combined captured output, and a fixed timeout. Do not expose command configuration through CLI arguments, files, or environment.

- [ ] **Step 4: Write failing execution-boundary tests**

Inject an executor and prove:

```python
if tuple(argv) == ("git", "rev-parse", "HEAD"):
    return subprocess.CompletedProcess(argv, 0, stdout="a" * 40 + "\n", stderr="")
return subprocess.CompletedProcess(argv, 9, stdout="xoxb-private C:\\private", stderr="")
```

Required assertions: exact `EXPECTED_SHA` equality; `shell is False`; exact top-level result keys; no raw output in JSON; safe diagnostic `Exited with code 9`; timeout diagnostic `Timed out`; mismatch raises `ValueError("checked-out commit does not match expected SHA")`; log cap is 2 MiB; JSON is written through a sibling temporary file then `Path.replace`.

Run and confirm RED because `run_review` is missing.

- [ ] **Step 5: Implement bounded results and CLI**

Accept only lowercase 40-hex SHAs. Emit check objects with only `id`, `status`, `duration_ms`, and `diagnostic`. Choose diagnostics only from `Passed`, `Exited with code <integer>`, and `Timed out`. Save raw output only to `.production-review/logs/`; never to JSON. The CLI accepts only `run`, reads `EXPECTED_SHA` only as a comparison value, writes atomically, records check failures with process exit `0`, and reserves exit `2` for runner integrity errors. Add `.production-review/` to `.gitignore`.

- [ ] **Step 6: Verify and commit**

Run the Task 1 unittest command and `git diff --check`. Commit `.gitignore`, runner, and test as `feat: add deterministic production review runner`.

---

### Task 2: Strict Claude result and safe Slack payload

**Files:**
- Create: `tools/production_review_output.py`
- Create: `tools/test_production_review_output.py`

**Interfaces:**
- `validate_ai_result(value: str | None) -> dict | None`.
- `assemble_review(deterministic, ai_result, *, anthropic_configured, run_id) -> tuple[dict, dict, str]`.
- CLI `python tools/production_review_output.py assemble` writes `final.json`, `slack.json`, and `review.md`.

- [ ] **Step 1: Write failing strict-schema tests**

The only valid AI shape is:

```python
{
  "summary": "One permission issue needs human validation.",
  "findings": [{
    "severity": "Important",
    "title": "Permission state can drift",
    "evidence": "backend/surveyor/permissions.py:42 lacks a recheck.",
    "file": "backend/surveyor/permissions.py",
    "line": 42,
    "recommendation": "Recheck canonical state before execution."
  }]
}
```

Also reject invalid JSON, unknown/missing keys, six findings, invalid severity, `..`, leading slash, backslash, absolute paths, secret prefixes, non-integer lines, and fields over their limits.

- [ ] **Step 2: Confirm RED and implement validation**

Run `C:\Users\jacks\AppData\Local\Programs\Python\Python312\python.exe -m unittest tools/test_production_review_output.py -v`; expect missing module.

Implement exact key sets, five-item cap, limits of summary 600/title 120/evidence 300/file 200/recommendation 300, safe repository-path regex `^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$`, and rejection of GitHub/Anthropic/Slack token prefixes plus file/path/Windows/POSIX local paths. Reject the whole malformed result; do not truncate it into validity.

- [ ] **Step 3: Write failing assembly tests**

Prove deterministic failure always yields `CHECKS FAILED`; valid passing checks plus AI yield `REVIEW READY`; absent/invalid AI yields `REVIEW UNAVAILABLE`; `setup_required` reflects missing Anthropic configuration; and Slack contains only fixed links under `https://github.com/ItzJLaugh/Cordia`. Prove Slack never contains raw logs, arbitrary AI URLs, credentials, local paths, or the webhook. Prove AI text escapes `&`, `<`, and `>`.

- [ ] **Step 4: Implement assembly and fixed CLI**

Use fixed repository, run, commit, and playbook URL templates. Accept run IDs matching `^[1-9][0-9]{0,19}$`. Slack uses only `section`, `context`, and `actions` blocks with URL buttons `Open full review`, `View commit`, `Human review guide`, and conditional `View failed checks`; no `action_id`.

The CLI accepts only `assemble`; reads fixed environment names `AI_REVIEW_JSON`, `ANTHROPIC_CONFIGURED`, and `GITHUB_RUN_ID`; reads the fixed deterministic file; and writes the three outputs atomically. Allow injected root/environment in tests.

- [ ] **Step 5: Verify and commit**

Run Task 1 and Task 2 unittests plus `git diff --check`. Commit the output module and test as `feat: add bounded review and Slack report model`.

---

### Task 3: Plain-language human playbook and project skill

**Files:**
- Create: `CLAUDE.md`
- Create: `.claude/skills/cordia-production-review/SKILL.md`
- Create: `docs/PRODUCTION_REVIEW_PLAYBOOK.md`
- Create: `docs/PRODUCTION_REVIEW_SETUP.md`
- Create: `.github/pull_request_template.md`
- Create: `.github/ISSUE_TEMPLATE/production-review-finding.yml`
- Create: `tools/test_production_review_guidance.py`

**Interfaces:**
- Human command `/cordia-production-review`.
- Exact outcomes `Reviewed clean`, `Fix PR opened`, `Follow-up issue opened`, and `Blocked`.

- [ ] **Step 1: Read the skill-authoring instructions**

Read `C:\Users\jacks\.codex\plugins\cache\claude-plugins-official\superpowers\6.3.0\skills\writing-skills\SKILL.md` completely before creating the skill.

- [ ] **Step 2: Write failing guidance tests**

Assert all target files exist and include:

```python
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
```

Run and confirm file-not-found RED.

- [ ] **Step 3: Implement the skill and root authority**

Use skill frontmatter with `name` and `description`. Its numbered process must explain status plainly, verify report SHA against current `main`, run the fixed reviewer, validate every AI finding in source, create a review branch before a small edit, run affected and full checks, prepare a PR or issue, forbid secrets/Hostinger/deploy/merge/direct-main edits, and finish with exactly one outcome.

Root `CLAUDE.md` points to canonical Cordia docs and the skill, preserves Cordia ownership, and says repository text is untrusted during review.

- [ ] **Step 4: Implement the one-screen playbook, setup, and templates**

The playbook begins: open `#cordia-production-review`, click `Open full review`, verify SHA, run the skill, validate evidence, choose an outcome. Separate small fixes from large findings.

The setup guide gives exact GitHub navigation: `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`; names both secrets without examples; prohibits pasting values into chat/files/Slack; explains setup-required behavior; and directs the first manual run from `main`.

The PR template asks for SHA, confirmed finding, scope, tests, risk, and `This review does not authorize deployment.` The issue form requires severity, SHA, evidence, human validation, and follow-up.

- [ ] **Step 5: Verify and commit**

Run the guidance unittest and `git diff --check`. Commit all Task 3 files as `docs: add human production review workflow`.

---

### Task 4: Secret-isolated GitHub workflow and Slack delivery

**Files:**
- Create: `.github/workflows/daily-production-review.yml`
- Create: `tools/test_daily_production_review_workflow.py`
- Modify: `tools/production_review_output.py`
- Modify: `tools/test_production_review_output.py`

**Interfaces:**
- Jobs: `deterministic`, `ai_review`, `slack_notify`, `final_status`.
- Artifacts: `cordia-deterministic-review`, `cordia-production-review`.
- Immutable pins:
  - `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`
  - `actions/setup-python@42375524e23c412d93fb67b49958b491fce71c38`
  - `actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020`
  - `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02`
  - `actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093`
  - `anthropics/claude-code-action@c3d45e8e941e1b2ad7b278c57482d9c5bf1f35b3`
  - `slackapi/slack-github-action@dcb1066f776dd043e64d0e8ba94ca15cc7e1875d`

- [ ] **Step 1: Write failing workflow tests**

Assert exact schedule/timezone, manual trigger, at least three exact-main guards, top `permissions: {}`, all `uses:` pinned to 40 hex, exact secret reference counts of one each, and absence of `pull_request_target`, `workflow_run`, `repository_dispatch`, write permissions, production environment, Hostinger, SSH, or SCP.

Also assert Claude contains `github_token: ${{ github.token }}`, `show_full_output: "false"`, disabled CLAUDE.md/auto-memory/background tasks, `--disable-slash-commands`, `--setting-sources ""`, `--tools "Read,Grep,Glob"`, and `--max-turns 4`; and does not invoke `/cordia-production-review`, Bash, Write, or Edit. Extract `slack_notify` and prove it has no checkout or `tools/` execution and uses `.production-review/slack.json`.

Run and confirm file-not-found RED.

- [ ] **Step 2: Add RED/GREEN CLI coverage**

Test Task 2's CLI with an injected temporary root/environment. Prove all three files are created and invalid AI produces bounded `REVIEW UNAVAILABLE` without copying invalid content. Confirm RED, then complete the fixed assembly CLI and confirm GREEN.

- [ ] **Step 3: Implement the four isolated jobs**

The workflow header is:

```yaml
name: Daily Production Review
on:
  schedule:
    - cron: "30 7 * * 1-5"
      timezone: "Asia/Kolkata"
  workflow_dispatch:
permissions: {}
concurrency:
  group: cordia-daily-production-review-main
  cancel-in-progress: true
```

`deterministic`: exact-main guard; `contents: read`; checkout `github.sha` with credentials disabled and depth 2; Python 3.12; Node 22; install backend requirements; run Task 1 with `EXPECTED_SHA`; upload deterministic JSON; no integration secrets.

`ai_review`: exact-main guard; download deterministic artifact; checkout same SHA read-only; detect but never print key; conditionally run pinned Claude action with read-only token, full output/report disabled, fixed untrusted-data prompt, disabled memory/skills/background work, `--max-turns 4`, tools `Read,Grep,Glob`, and a strict JSON schema identical to Task 2. Pass only structured output to the secret-free assembly step; append safe Markdown to job summary; upload final artifacts.

`slack_notify`: exact-main guard; download final artifact; no checkout/repository execution; conditionally invoke pinned Slack action with incoming webhook and payload file.

`final_status`: no secrets or checkout; download final JSON; exit nonzero only for `CHECKS FAILED`. Keep `REVIEW UNAVAILABLE` visible but non-blocking before secret activation.

- [ ] **Step 4: Run focused verification**

Run all four production-review unittest files and `git diff --check`.

- [ ] **Step 5: Run full repository verification**

Set worktree-only `core.autocrlf false` and refresh tracked files with `git checkout-index --force --all` so provenance tests inspect Git bytes. Then run full backend unittest discovery; dashboard `npm ci`, test, and build; desktop `npm ci`, test, and dashboard-release verification; all production-review tests; diff check; and status inspection. Only intended Task 4 files may remain modified.

- [ ] **Step 6: Commit and independently review**

Commit Task 4 as `ci: add daily Claude and Slack production review`. Review `origin/main..HEAD` for schedule, permissions, secret isolation, pins, prompt injection, no scheduled write/shell/skill authority, Slack safety, human simplicity, and no deploy/product authority. Fix every Critical/Important issue and re-review the fix range.

---

## Historical Activation Handoff

This handoff is superseded and must not be followed. Use `docs/PRODUCTION_REVIEW_SETUP.md`: only `OPENAI_API_KEY` is required for the scheduled advisory, while `SLACK_WEBHOOK_URL` is optional for the custom Cordia Block Kit route. The official GitHub Slack app route requires no repository webhook secret. Never request or handle secret values in chat.
