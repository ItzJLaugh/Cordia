# Sprint 1 Task 1 Report

## Baseline result

Reuse pass. The new framework contract test passed against the existing
`build_context`, `run_turn`, and `apply_proposal` functions without production
changes. No RED was fabricated.

## Files changed

- `backend/tests/test_mvp_framework.py`
- `docs/CORDIA_MVP_FRAMEWORK.md`
- `.superpowers/sdd/2026-08-22-cordia-mvp-sprint-1/task-1-report.md`

## Verification

All commands were run from `backend` unless noted.

| Command | Result |
| --- | --- |
| `py -3 -m unittest discover -s tests -p "test_mvp_framework.py" -v` | 1 test passed; first sandbox launch returned `Access is denied`, then the same command passed outside the sandbox |
| `py -3 -m unittest discover -s tests -p "test_cordia_agent.py" -v` | 13 tests passed |
| `py -3 -m unittest discover -s tests -p "test_workspace_turn_route.py" -v` | 14 tests passed; expected optional dependency/environment warnings only |
| `git diff --check` | passed; only Git line-ending warnings |

## Evidence label

**Simulated.** The test uses a deterministic model double and exercises the
real Cordia kernel path. No provider, connector, skill, network, secret, or
live deployment was called or verified.

## Self-review

- The workspace uses the required `workspace_demo`, revision `0`, `Demo`, and
  empty state collections.
- The simulated envelope uses the exact `status_api`, `Status API`, `api_key`,
  and `Read service status.` values.
- The test captures system, user, and `max_tokens` arguments, checks memory
  policy propagation, fixed server-owned speech, revision `1`, and the pending
  action kind.
- The framework disposition table matches the task brief verbatim.
- No unrelated files were changed.

## Commit

Task-only commit created with message `test: prove the Cordia MVP kernel path`.

## Round 1/5 follow-up

The framework test now asserts the exact public connector action shape, with no
`display_name` or `purpose`, and the exact structured pending action retaining
`display_name`, `setup_kind`, and `purpose`. The assertions passed immediately;
this is reuse/boundary evidence and required no production change.

| Command | Result |
| --- | --- |
| `py -3 -m unittest discover -s tests -p "test_mvp_framework.py" -v` | 1 test passed |
| `py -3 -m unittest discover -s tests -p "test_cordia_agent.py" -v` | 13 tests passed |
| `py -3 -m unittest discover -s tests -p "test_workspace_turn_route.py" -v` | 14 tests passed; expected optional dependency/environment warnings only |
| `git diff --check` | passed; Git line-ending warning only |

Self-review: only the requested literal assertions and this report update were
made; public provider fields are now explicitly protected from the public
receipt while preserved in the structured pending action. Evidence remains
**Simulated**; no provider, connector, skill, network, secret, or live system
was called.
