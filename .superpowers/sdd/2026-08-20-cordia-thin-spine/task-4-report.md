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
