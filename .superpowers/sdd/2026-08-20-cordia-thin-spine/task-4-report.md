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

## Review-fix round 2

- Canonical saves now require the caller's expected revision and compare the complete candidate revision under the owner-workspace `FOR UPDATE` row lock. A stale human, connector, runtime, or interface snapshot returns a conflict without overwriting canonical state; a changed save increments once, while unchanged state does not.
- The human mutation route returns the actual saved canonical workspace, including its persisted revision, and returns the actual current workspace on conflict instead of echoing a pre-save candidate.
- The shared privacy boundary now also rejects relative slash/backslash paths and single-component POSIX paths in turn input, speech, and all permitted proposal text, while retaining validated HTTPS URLs.
- Speak truth semantics now reject reviewed declarative status/completion wording, including GitHub and first-person past/perfect claims, while allowing questions and the explicit conditional statement that a connector is available after approval.
- The empty-workspace greeting now requires non-whitespace compiled memory.

### Review-fix round 2 verification

- RED/GREEN covered stale save signatures/interleavings, relative-path privacy cases, false declarative speak claims versus allowed questions/conditions, and whitespace-only memory greeting.
- Focused/adjacent GREEN: Cordia Agent (11), production-store workspace turns (5), workspace-turn route (6), operator profile (12), and agent-turn dashboard test (4).
- Full backend: 232/233 passed. The unchanged failure is the optional embedding runtime dependency (`sentence_transformers` is not installed).
- Full dashboard: `npm.cmd test` passed 88/88. `git diff --check` passed.
- The production-store test uses a deterministic transaction double that records the real production `FOR UPDATE` SQL and interleaves production store calls. It validates the compare-and-save semantics but is not a multi-process PostgreSQL contention test.

## Review-fix round 3

- Speak truth validation now evaluates punctuation-delimited clauses independently. A question or conditional availability clause no longer exempts an earlier false completion claim in the same response.
- Added first-person completion detection for contracted, past-perfect, and successful perfect forms while retaining questions and genuine conditional/future language.
- Replaced generic slash-pair rejection with structural local-path evidence: dot paths, drive/UNC paths, absolute paths, known sensitive segments, and filename-shaped relative paths are rejected. Ordinary review pairs (`human/AI`, `yes/no`, `client/server`, `HTTP/2`) and validated HTTPS URLs remain allowed.
- Generic status wording is limited to terminal backend-status predicates: relational `connected to/with` and catalog availability language remain valid.

### Review-fix round 3 verification

- RED/GREEN: clause-mixed truth claims, first-person variants, relative structural paths, safe slash-separated review terms, and relational/catalog status language.
- Focused/adjacent GREEN: Cordia Agent (11), operator profile (13), workspace-turn route (6), workspace-turn store (5).
- Full dashboard: `npm.cmd test` passed 88/88. No provider or connector execution was attempted.
- Full backend: 233/234 passed. The unchanged failure is the optional embedding runtime dependency (`sentence_transformers` is not installed). `git diff --check` passed.

## Review-fix round 4

- Replaced accumulated speak exceptions with a bounded clause classifier. Interrogative clauses and clauses explicitly beginning `if`, `when`, `unless`, `whether`, `suppose`, or `assuming` are treated as discussion only; each remaining declarative clause is checked independently.
- Declarative completion claims by Cordia, the agent, the assistant, I, or we now reject flexible completed/approved/executed/run/deployed/created forms. Backend-state predicates reject connector, integration, account, service, app, repository, workspace, skill, and action subjects or objects, plus bounded connector names projected from the safe workspace context.
- Explanatory catalog/approval availability and non-backend relations remain allowed. A question or conditional clause cannot excuse a false declarative clause beside it.
- The shared path boundary now rejects a leading absolute slash or backslash such as `/project` or `\\secret` after safe remote URLs are excluded, while preserving HTTPS/IPv6 URLs and ordinary slash-separated review text.

### Review-fix round 4 verification

- RED/GREEN: compact clause-role classifier table, context-bounded GitHub name, agent completion variants, backend-object claims, mixed clauses, absolute slash/backslash paths, safe URLs, and normal slash review terms.
- Focused/adjacent GREEN: Cordia Agent (13), operator profile (13), workspace-turn route (6), workspace-turn store (5).
- Full dashboard: `npm.cmd test` passed 88/88. Full backend: 235/236 passed; the unchanged failure is the optional embedding runtime dependency (`sentence_transformers` is not installed).
- `git diff --check` passed. No provider call or connector execution was attempted; provider evidence remains `Not yet verified`.
