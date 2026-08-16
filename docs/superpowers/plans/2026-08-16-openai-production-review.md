# OpenAI Production Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the scheduled Anthropic review step with a bounded OpenAI Responses API reviewer while preserving the existing deterministic checks, 7:30 AM India schedule, strict report validator, Slack isolation, and human-only action boundary.

**Architecture:** A new standard-library Python adapter builds a capped review context from the exact checked-out commit, sends one tool-free Responses API request to the pinned `gpt-5.4-mini-2026-03-17` snapshot, validates the structured response, and atomically writes only the bounded result. The existing artifact assembler remains the single output authority and is made provider-neutral; the workflow supplies the OpenAI secret to exactly one step and continues to fail closed when the key or API result is unavailable.

**Tech Stack:** Python 3.12 standard library (`urllib`, `subprocess`, `json`), GitHub Actions YAML, Python `unittest`.

**Spec:** `docs/superpowers/specs/2026-08-15-cordia-daily-production-review-design.md`

## Global Constraints

- The schedule remains exactly `cron: "30 7 * * 1-5"` with `timezone: "Asia/Kolkata"`, plus `workflow_dispatch`.
- The workflow runs only for exact `refs/heads/main`; top-level permissions remain `{}` and review jobs have at most `contents: read`.
- The OpenAI secret name is exactly `OPENAI_API_KEY`; it appears as a GitHub secret reference exactly once and is available to exactly one network step.
- The model is pinned to exactly `gpt-5.4-mini-2026-03-17`; the API endpoint is exactly `https://api.openai.com/v1/responses`; `store` is `false`; no model tools are configured.
- The request uses strict Structured Outputs matching the existing `summary` plus at-most-five `findings` schema.
- Repository data is untrusted review input. It must never gain instruction authority, shell authority, file-write authority, GitHub-write authority, merge authority, deployment authority, Hostinger access, or arbitrary network authority.
- Review context must match the checked-out full 40-character SHA, contain only the bounded deterministic result and bounded text from the first-parent commit diff/changed files, and be capped at 120,000 characters total and 24,000 characters per changed file.
- The adapter must never print or persist the API key, request headers, raw API error body, raw API response, or review context.
- Missing key, SHA mismatch, HTTP/API failure, refusal, incomplete response, invalid JSON, or invalid schema produces `REVIEW UNAVAILABLE`; deterministic failures remain authoritative.
- Existing Slack behavior remains optional and isolated; no Slack webhook is required to run or retain the GitHub review.
- Do not add the OpenAI SDK or any production dependency; use the Python standard library.

---

### Task 1: Bounded OpenAI Responses Adapter

**Files:**
- Create: `tools/openai_production_review.py`
- Create: `tools/test_openai_production_review.py`

**Interfaces:**
- Consumes: `.production-review/deterministic.json`, `EXPECTED_SHA`, `OPENAI_API_KEY`, the exact checked-out Git repository, and `production_review_output.validate_ai_result`.
- Produces: `tools/openai_production_review.py run` and, only on a fully valid completed response, `.production-review/openai-review.json` containing exactly the validated `{summary, findings}` object.

- [ ] **Step 1: Write failing adapter contract tests**

Add `unittest` coverage that imports `openai_production_review.py` and asserts:

```python
def test_request_is_tool_free_pinned_and_strict(self):
    body = self.module.build_request("bounded context")
    self.assertEqual(body["model"], "gpt-5.4-mini-2026-03-17")
    self.assertFalse(body["store"])
    self.assertNotIn("tools", body)
    self.assertEqual(body["text"]["format"]["type"], "json_schema")
    self.assertTrue(body["text"]["format"]["strict"])

def test_context_requires_exact_sha_and_is_bounded(self):
    context = self.module.build_review_context(
        repo_root,
        deterministic_path,
        expected_sha,
        run_git=fake_git,
    )
    self.assertLessEqual(len(context), 120_000)
    self.assertIn(expected_sha, context)
    self.assertNotIn("ignored binary bytes", context)

def test_completed_response_writes_only_validated_result(self):
    exit_code = self.module.main(
        ["run"], repo_root=temp_root, environ=valid_environment,
        opener=fake_completed_response,
    )
    self.assertEqual(exit_code, 0)
    self.assertEqual(json.loads(output_path.read_text()), valid_ai_object)

def test_api_failure_and_invalid_response_fail_closed_without_leakage(self):
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = self.module.main(
            ["run"],
            repo_root=temp_root,
            environ=valid_environment,
            opener=failing_opener,
            run_git=fake_git,
        )
    self.assertNotEqual(exit_code, 0)
    self.assertFalse(output_path.exists())
    self.assertNotIn(api_key, stdout.getvalue() + stderr.getvalue())
```

Also cover missing key, mismatched SHA, malformed percent/Unicode text handling, response refusal/incomplete status, multiple or absent `output_text` items, invalid report schema, stale-output removal, constant endpoint, bearer header set only on the request object, capped changed-file count/content, and no `.env`/key/private-key file inclusion.

- [ ] **Step 2: Run the focused tests and record RED**

Run:

```powershell
py -3.12 -m unittest tools.test_openai_production_review -v
```

Expected: fail because `tools/openai_production_review.py` does not exist.

- [ ] **Step 3: Implement the minimal standard-library adapter**

Create a focused module with constants `MODEL = "gpt-5.4-mini-2026-03-17"`, `RESPONSES_URL = "https://api.openai.com/v1/responses"`, `MAX_CONTEXT_CHARS = 120_000`, and `MAX_FILE_CHARS = 24_000`. Its exact public call signatures are `build_review_context(repo_root: Path, deterministic_path: Path, expected_sha: str, *, run_git=subprocess.run) -> str`, `build_request(context: str) -> dict`, `extract_output_text(response: dict) -> str | None`, `request_review(api_key: str, body: dict, *, opener=urllib.request.urlopen) -> dict | None`, and `main(argv=None, *, repo_root=None, environ=None, opener=None, run_git=None) -> int`.

Use fixed argument arrays and `shell=False` for Git. Confirm `HEAD`, `EXPECTED_SHA`, and deterministic `commit` are the same full SHA. Build context from deterministic JSON, `git diff --no-ext-diff --unified=3 HEAD^ HEAD --`, and capped UTF-8 text for safe changed paths from `git diff --name-only HEAD^ HEAD --`. Exclude binary/unreadable data, `.env*`, credential/key/private-key files, and path traversal. Label all repository content as untrusted data inside fixed delimiters.

Build one Responses API body with `instructions`, `input`, `reasoning: {"effort": "medium"}`, `text.verbosity: "low"`, strict `text.format` JSON schema, `max_output_tokens: 4000`, and no `tools`. Send via `urllib.request.Request` with fixed endpoint, JSON content type, and bearer authorization. Require a completed response with exactly one assistant `output_text`, validate it through `production_review_output.validate_ai_result`, and atomically publish only that validated object. Remove any stale output before every attempt. Catch network, timeout, decoding, response-shape, and filesystem errors with a fixed non-sensitive diagnostic and nonzero exit.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
py -3.12 -m unittest tools.test_openai_production_review -v
```

Expected: all adapter tests pass with no live network request.

- [ ] **Step 5: Commit Task 1**

```powershell
git add -- tools/openai_production_review.py tools/test_openai_production_review.py
git commit -m "feat: add bounded OpenAI production reviewer"
```

### Task 2: Provider-Neutral Workflow, Outputs, and Setup

**Files:**
- Modify: `.github/workflows/daily-production-review.yml`
- Modify: `tools/production_review_output.py`
- Modify: `tools/test_daily_production_review_workflow.py`
- Modify: `tools/test_production_review_output.py`
- Modify: `tools/test_production_review_guidance.py`
- Modify: `docs/PRODUCTION_REVIEW_SETUP.md`
- Modify: `docs/superpowers/specs/2026-08-15-cordia-daily-production-review-design.md`

**Interfaces:**
- Consumes: Task 1's `python tools/openai_production_review.py run` and `.production-review/openai-review.json`.
- Produces: a scheduled/manual workflow that uses only `OPENAI_API_KEY`, provider-neutral `AI advisory` artifacts, and unchanged bounded final/Slack models.

- [ ] **Step 1: Write failing workflow/output/guidance migration tests**

Update structural tests to assert exactly one `${{ secrets.OPENAI_API_KEY }}` reference, zero Anthropic secret/action references, an exact-main guarded OpenAI script step, Python 3.12 setup, `fetch-depth: 2`, key blanking on every other AI-job step, no provider secret in deterministic/Slack/final jobs, and the unchanged schedule/manual triggers. Assert the only action set is the already pinned checkout/setup/upload/download/Slack actions.

Update output tests to call:

```python
assemble_review(deterministic, ai_result, model_configured=True, run_id="123")
```

and require the human surfaces to say `AI advisory` rather than `Claude advisory`, while the final JSON schema and Slack fixed-link model remain unchanged. Update CLI tests to pass `AI_REVIEW_PATH` and `MODEL_REVIEW_CONFIGURED` and prove absent/invalid files produce `REVIEW UNAVAILABLE` without copying raw content.

Update guidance tests to require `OPENAI_API_KEY`, the pinned model identifier, optional Slack/GitHub-app guidance, and no `ANTHROPIC_API_KEY` in production-review setup/spec files. Do not rename the existing human-invoked `.claude` skill; it remains a local developer tool rather than the scheduled model provider.

- [ ] **Step 2: Run the focused migration tests and record RED**

Run:

```powershell
py -3.12 -m unittest tools.test_daily_production_review_workflow tools.test_production_review_output tools.test_production_review_guidance -v
```

Expected: failures because the workflow and artifacts still name Anthropic/Claude.

- [ ] **Step 3: Wire the OpenAI adapter and provider-neutral artifacts**

Replace the Claude Action step with a `run: python tools/openai_production_review.py run` step. Supply `OPENAI_API_KEY` and `EXPECTED_SHA` only to that step, continue on API failure, and set `MODEL_REVIEW_CONFIGURED` from whether the step was skipped. Set `AI_REVIEW_PATH` to `.production-review/openai-review.json`. Keep assembly, summary, retention, Slack, and final-status behavior intact. Add pinned Python setup to the AI job and use two-commit checkout depth.

Change `production_review_output.py` to load and validate the bounded AI file, accept `model_configured`, and render `AI advisory` labels. Preserve the exact final JSON keys and states so downstream consumers do not fork. Update setup/spec language from Anthropic/Claude scheduled provider to OpenAI Responses API and document that the official GitHub Slack app can provide workflow notifications without `SLACK_WEBHOOK_URL`; the webhook remains optional only for the custom Cordia Block Kit summary.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
py -3.12 -m unittest tools.test_openai_production_review tools.test_daily_production_review_workflow tools.test_production_review_output tools.test_production_review_guidance -v
```

Expected: all focused tests pass.

- [ ] **Step 5: Run full repository verification**

Run:

```powershell
py -3.12 -m unittest discover -s backend/tests -v
py -3.12 -m unittest discover -s tools -p "test_*.py" -v
Set-Location dashboard-app; npm.cmd ci; npm.cmd test; npm.cmd run build; Set-Location ..
Set-Location desktop; npm.cmd ci; npm.cmd test; npm.cmd run verify:dashboard-release; Set-Location ..
git diff --check
```

Expected: backend, tools/review, dashboard, desktop, production build, release provenance, and diff checks all pass. Record but do not conceal pre-existing dependency-audit findings if installation reports them.

- [ ] **Step 6: Commit Task 2**

```powershell
git add -- .github/workflows/daily-production-review.yml tools/production_review_output.py tools/test_daily_production_review_workflow.py tools/test_production_review_output.py tools/test_production_review_guidance.py docs/PRODUCTION_REVIEW_SETUP.md docs/superpowers/specs/2026-08-15-cordia-daily-production-review-design.md docs/superpowers/plans/2026-08-16-openai-production-review.md
git commit -m "feat: run daily production review with OpenAI"
```
