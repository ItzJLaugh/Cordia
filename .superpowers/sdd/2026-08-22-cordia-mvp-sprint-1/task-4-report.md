# Task 4 report: Real Authenticated Provider Proof

Source commit before evidence: `6441c39f383d3fda4c0f6b4d52b0ef73d73e60c9`
Verification time: `2026-08-24T06:57:36Z`

## Result boundary

Status: Not yet verified with OpenAI.
Reason: No approved server-side OpenAI credential was available.

Configuration readiness is not provider verification. Deterministic doubles are simulated evidence. No provider call or authenticated application observation was attempted.

## Required deterministic comparisons

| Exact command | Fresh result |
|---|---|
| `py -3 -m unittest discover -s tests -p "test_mvp_framework.py" -v` | 1/1 passed |
| `py -3 -m unittest discover -s tests -p "test_model_provider.py" -v` | 10/10 passed |
| `py -3 -m unittest discover -s tests -p "test_workspace_turn_route.py" -v` | 17/17 passed |
| `py -3 -m unittest discover -s tests -p "test_workspace_turn_store.py" -v` | 11/11 passed |
| `npm.cmd test` | 99/99 passed |
| `npm.cmd run build` | passed; 204 modules transformed and the dashboard release was rebuilt |

The focused backend total is 39/39. These results prove implemented contracts against doubles and local state models only. They do not prove OpenAI connectivity or an authenticated provider observation.

## Complete backend comparison

Command: `py -3 -m unittest discover -s tests -v`

Fresh result after the optional-runtime test boundary correction: 272 tests ran; 271 passed; 1 explicitly skipped optional shadow-scorer runtime test; exit 0. `test_declared_runtime_can_import_the_shadow_scorer` skips only when one or more required optional modules (`numpy`, `sentence_transformers`, or `faiss`) are unavailable. In an installed runtime, it still executes the real subprocess import and callable assertion. The shadow scorer itself remains unverified in this environment.

The first comparison before `6441c39` had two additional errors. Focused reproduction showed that two older route tests did not double the Task 3 `workspace_turn_usage` store interface, so each fell through to a real database connection. Task 4 made no production or test patch. Commit `6441c39` updated those fixtures, scoped review was clean, and the fresh complete comparison returned to the one known optional runtime boundary; this correction makes that boundary an explicit skip.

## Safe configuration-presence check

The presence-only check used `Test-Path` against these environment names and fixed configuration-file locations. It did not read or print any value.

| Presence check | Result |
|---|---|
| `LLM_KEY` | absent |
| `LLM_MODEL` | absent |
| `LLM_BASE_URL` | absent |
| `CORDIA_PG_DSN` | absent |
| repository environment file | absent |
| backend environment file | absent |
| fixed server environment file | absent |

Because the approved server-side credential was absent, an authenticated observation was not possible. The task stopped at the required boundary without requesting a credential.

## Dashboard release provenance

The first clean-HEAD verifier run correctly rejected the previously committed release because the committed JavaScript bundle name did not match a clean rebuild. Rebuilding from the current dashboard source produced `index-DADi2U6-.js`, the existing CSS bundle, a regenerated index, and a regenerated SHA-256 provenance manifest.

The repository verifier rebuilt the committed dashboard from a clean dependency install and matched every committed output byte. It verified source hash `8568ab092cf77df107ce36547a6ffbb78de5c6a48f8c75e4603fa21f01e58bea`.

## Bounded evidence inspection

- Evidence contains no model output, test message, account identifier, credential, configuration value, session material, or machine location.
- The manual tells a human how to sign in, complete Surveyor, confirm compiled memory, send one workspace message, reload, inspect duplicate replay, check the ten-turn limit, recover from failures, and label evidence truthfully.
- Generated dashboard output is limited to the index, hashed bundles, and build-provenance manifest.
- High-confidence credential-shape matches: 0.
- Canonical test-message matches: 0.
- Machine-location matches: 0.
- Short `sk-` substring matches in generated assets were traced to ordinary minified class-name text, not credential shapes; the high-confidence scan remained at 0.

## Final checks

- Staged diff check: passed for the evidence, manual, report, and regenerated dashboard release only.
- Leakage inspection: passed with 0 high-confidence credential-shape, canonical test-message, or machine-location matches.
- Committed-HEAD dashboard reproducibility: passed; clean rebuild matched the committed index, CSS, JavaScript, and provenance manifest.

## Self-review

- Simulated, configured, locally verified, live verified, and not verified are kept distinct.
- The optional shadow-scorer runtime skip is named; the clean backend exit does not claim that scorer itself is verified.
- No live or deployment claim is made.
- No connector or skill execution was introduced.
- No deploy, push, publish, or merge was performed.

## Optional shadow-scorer runtime boundary correction

Before: `py -3 -m unittest discover -s tests -p test_embedding_runtime.py -v` ran 1 test in 0.184s and failed with `ModuleNotFoundError: No module named 'sentence_transformers'` from the real `embedding_scoring` subprocess import.

After: the same focused command ran 1 test in 0.000s and exited 0 with 1 explicit skip: `optional shadow-scorer runtime dependencies unavailable: sentence_transformers, faiss`.

Final full comparison: `py -3 -m unittest discover -s tests -v` ran 272 tests in 25.502s and exited 0: 271 passed and 1 explicitly skipped optional shadow-scorer runtime test. The scorer remains unverified in this environment.

Final focused Sprint backend comparison: 39/39 passed (`test_mvp_framework.py` 1/1, `test_model_provider.py` 10/10, `test_workspace_turn_route.py` 17/17, and `test_workspace_turn_store.py` 11/11).
