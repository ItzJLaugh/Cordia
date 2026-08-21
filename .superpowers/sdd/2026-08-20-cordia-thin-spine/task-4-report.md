# Task 4 report: Five-Envelope Cordia Agent and Workspace Turn

## Delivered

- Added strict validation for the five permitted Cordia Agent envelopes and the revisioned idempotent turn request.
- Added bounded prompt construction from compiled memory, explicit safe workspace summaries, and bounded prior turns. Raw profiles, payloads, paths, secret references, ciphertext, and reasons are excluded.
- Added canonical `revision` and `pending_actions`; speak turns preserve the revision, while persisted proposals increment it exactly once.
- Replaced `POST /surveyor/run` with the owner-scoped workspace turn transaction, including idempotency replay and revision-conflict responses. Connector operations are not executed.
- Added the revisioned browser request, truthful empty-workspace greeting, safe action card projection, and one-refresh-on-new-revision interaction.
- Recorded the real-provider gate as `Not yet verified`; no configured credential was present and no fake evidence was created.

## Red/green evidence

- RED backend: `py -3 -m unittest discover -s tests -p test_cordia_agent.py -v` initially failed because `surveyor.cordia_agent` did not exist.
- RED dashboard: `node --test test/agent-turn.test.js test/api.test.js` initially failed because the agent response model and revisioned request contract did not exist.
- GREEN backend: model provider (7), Cordia Agent (8), workspace turn route (5), and adjacent workspace state (13) tests passed.
- GREEN dashboard: `npm.cmd test` passed 88 tests, including the rendered production Assistant interaction.
- `git diff --check` passed.

## Remaining evidence boundary

`docs/evidence/cordia-thin-spine-real-provider.md` is intentionally `Not yet verified`. The worktree had no approved `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_KEY` configuration, so no authenticated production route call was attempted.

## Review-fix round 1

- Canonical `save_workspace` now locks and increments `revision` whenever its persisted state changes. The production-store regression exercises human, connector, runtime, and interface-style changes, then proves a stale workspace-turn commit conflicts rather than overwrites them.
- Workspace-turn persistence is now explicitly tagged `cordia_workspace_turn_v1`. Idempotency lookup, recent-turn history, and first-turn detection all require that tag and a non-null idempotency key; legacy runs fail closed and cannot influence a prompt or greeting.
- Prompt projection preserves artifact summaries through the second safe projection and includes only bounded connector truth (`implementation_status`, `lifecycle`, `runtime_status`) alongside safe display fields.
- Agent input, speech, and allowed proposal text now reuse the established credential/path-safe boundary. The regression matrix covers common provider tokens, token assignments, PEM text, relative/POSIX/Windows/UNC paths, and a permitted HTTPS URL.
- Speak envelopes reject bounded false claims that a connector, action, integration, setup, or skill was connected, executed, run, completed, or approved. They may still ask, explain, or propose.
- Added production-store-function integration coverage for owner/workspace scoping, cross-owner rejection, idempotency replay, legacy exclusion, corrupt revision failure, and atomic stale-write conflict. Adjacent model-status and intent-miss tests now exercise the exact revisioned Task 4 request and compiled-memory boundary.

### Review-fix verification

- Independent RED/GREEN: Cordia Agent privacy/truth/prompt tests and production-store workspace-turn regressions were first added against the pre-fix behavior, then passed after the minimal store and agent changes.
- Focused and adjacent GREEN: Cordia Agent (11), production-store workspace turns (4), workspace-turn route (5), workspace state (13), model-status (2), and intent-miss runtime (1).
- Full backend: 230/231 passed. The sole failure remains the pre-existing optional embedding runtime dependency: `sentence_transformers` is not installed.
- Full dashboard: `npm.cmd test` passed 88/88.
- `git diff --check` passed. No real-provider call or connector execution was attempted; provider evidence remains `Not yet verified`.
