# Sprint 1 Task 3 Report

## Baseline

- The linked worktree was clean on `docs/cordia-thin-spine` before Task 3 edits.
- `py backend/tests/test_workspace_turn_store.py`: 5 passed.
- `py backend/tests/test_workspace_turn_route.py`: 14 passed, with the existing
  optional dependency and missing local DSN warnings.
- Dashboard `npm.cmd test`: 96 passed.
- The bare `python` command is not installed on this Windows PATH. The installed
  Python launcher initially returned `Access is denied` inside the file sandbox;
  the same deterministic tests ran successfully with the approved `py` launcher.

## Store RED evidence

Tests were added before changing `SCHEMA` or production store behavior. The
focused RED command was:

```powershell
py backend/tests/test_workspace_turn_store.py
```

It ran 10 tests with 1 failure and 4 errors:

- Four cases raised `AttributeError` because `workspace_turn_usage` did not
  exist.
- The shared-owner allowance case failed because turn 11 returned `committed`
  instead of `limit`.
- The deterministic transaction double records workspace and usage row locks
  and restores its snapshot when an injected run insert failure raises.

The initial tests cover turns 1 through 10 incrementing exactly once, turn 11
mutating neither workspace nor runs, duplicate replay after exhaustion, missing
and conflict paths, run-insert statement-failure rollback, two workspaces
sharing one owner allowance, an independent second owner, and bounded read-only
usage projection. Commit-phase failure coverage was added in review round 1
below; the initial report had incorrectly described the run-insert failure as a
failed-commit test.

## Minimal store change

- Added the brief's exact `surveyor_usage` table to `SCHEMA`.
- Added `workspace_turn_usage(email)`, which performs one read, creates no row
  or model work, and returns bounded integers with the fixed limit 10.
- Extended the existing `commit_workspace_turn` transaction in this order:
  workspace row lock, prior idempotency lookup, revision validation, usage row
  insert-if-absent, usage row `FOR UPDATE`, limit decision, workspace update,
  successful run insert, and one usage increment.
- The usage increment remains inside the same connection transaction and occurs
  only after the successful run insert.

Focused store GREEN:

```text
Ran 10 tests in 0.016s
OK
```

## Route and dashboard RED evidence

The route tests were added before route changes. The focused RED run executed 16
tests with 1 failure and 1 error:

- An exhausted owner still called the model and returned HTTP 200 instead of
  the exact HTTP 402 response.
- A simulated race returning transactional `status=limit` reached the old
  success branch and raised `KeyError: 'result'`.

The dashboard tests were added before client/UI changes. The focused command:

```powershell
npm.cmd test -- test/api.test.js test/agent-turn.test.js
```

ran 19 tests with 3 failures:

- Exact HTTP 402 usage-limit responses classified as generic errors.
- The usage-limit state helper did not exist.
- The rendered Assistant restored the draft but did not display the fixed
  upgrade copy.

## Minimal route and dashboard change

- Added the route usage precheck after prior replay and before artifact,
  context, and model work. It returns the exact fixed HTTP 402 body.
- Added the identical HTTP 402 handling for transactional `status=limit`,
  closing the cross-workspace race after model work without recording or
  charging the rejected call.
- Added an exact-key, exact-value HTTP 402 classifier. Extra keys, wrong values,
  wrong types, and unknown 402 bodies remain generic errors.
- Added one fixed usage-limit state transition that removes the optimistic user
  message, restores the draft, and displays only the server contract's fixed
  upgrade copy.
- `dashboard-app/src/WorkspaceView.jsx` was the one necessary file beyond the
  brief's list because it owns the rendered error-kind branch. The parent task
  explicitly approved this minimal import and branch; the rendered test covers
  it and verifies no workspace refresh occurs.

Focused GREEN results:

- Route: 16 passed immediately after the production change; final route suite
  is 17 passed after explicit missing-configuration non-consumption coverage.
- Dashboard API and agent-turn files: 19 passed.

## Concurrency and idempotency reasoning

- Same-workspace requests serialize on the workspace row. A waiter rechecks the
  stored run after acquiring that lock, so a duplicate returns `prior` before
  revision or allowance checks and never increments twice.
- Different workspaces for the same owner may pass the route's read-only
  precheck concurrently, but both serialize on the single owner usage row. At
  used 9, only one transaction can observe and consume the remaining turn; the
  other observes 10 and returns `limit` before workspace/run mutation.
- The workspace update, successful run insert, and usage increment share one
  transaction. The initial deterministic test proved rollback for a failed run
  insert, not for a commit-phase failure. Missing, validation, configuration,
  provider, conflict, replay, transactional limit, and statement-failure paths
  therefore do not consume usage. Review round 1 adds distinct commit-phase
  rollback evidence.
- Another email locks and increments a different usage row, so its allowance is
  independent.

## Final GREEN evidence

| Command | Result |
| --- | --- |
| `py backend/tests/test_workspace_turn_store.py` | 10 passed |
| `py backend/tests/test_workspace_turn_route.py` | 17 passed; existing optional dependency/local DSN warnings only |
| dashboard `npm.cmd test` | 99 passed |
| `git diff --check` | passed; Git line-ending warnings only |

## Evidence label

**Simulated.** All backend tests use deterministic in-memory/transaction
doubles, and dashboard tests use deterministic fetch doubles. No provider,
connector, skill, network, secret, credential, database service, or live
deployment was called or verified.

## Self-review

- Limit is exactly 10 successful committed model-backed turns per email across
  all workspaces.
- Duplicate replay precedes both route and transactional limit checks.
- The route precheck avoids provider cost for already exhausted owners; the
  locked transaction remains authoritative under concurrency.
- Both backend branches emit exactly `ok`, `error`, `code`, `used`, and `limit`
  with the required values and HTTP 402.
- Unknown HTTP 402 bodies fail closed as generic errors.
- Fixed server-owned speech, five-envelope validation, revision conflict
  recovery, connector/skill non-execution, and existing workspace ownership are
  unchanged.
- Only Task 3 implementation, tests, the approved rendered branch, and this
  report are included.

## Commit

Task-only commit message: `feat: enforce ten free Cordia Agent turns`.

## Review round 1/5: commit-phase rollback evidence

### Important finding

`backend/tests/test_workspace_turn_store.py:286` did not test the brief's
required failed-commit path. It injected a failure during `INSERT INTO
surveyor_runs`; the connection double could not fail during transaction commit.
The earlier "failed-commit rollback" wording was unsupported and has been
corrected above to "run-insert statement-failure rollback."

### RED evidence

A separate commit-phase test was added without changing the connection double.
It sets a one-shot `fail_commit` mode on `TurnConnection`, executes the real
`commit_workspace_turn`, expects `RuntimeError: simulated transaction commit
failure`, and asserts workspace, runs, and usage all match the pre-transaction
snapshot.

```text
py backend/tests/test_workspace_turn_store.py
Ran 11 tests in 0.016s
FAILED (failures=1)
AssertionError: RuntimeError not raised
```

This was the expected missing-double-behavior failure: the existing
`TurnConnection.__exit__` returned normally during the commit phase.

### Minimal test-double change

- Added `TurnConnection.fail_commit`, defaulting false.
- On a successful statement phase with `fail_commit` set, `__exit__` clears the
  one-shot flag, restores the full database snapshot, and raises the simulated
  commit failure.
- Renamed the original combined case to
  `test_statement_failure_and_uncommitted_paths_never_consume_usage`; it remains
  the separate run-insert statement-failure test.
- Added no production changes.

### GREEN evidence

| Command | Result |
| --- | --- |
| `py backend/tests/test_workspace_turn_store.py` | 11 passed |
| `py backend/tests/test_workspace_turn_route.py` | 17 passed; existing optional dependency/local DSN warnings only |
| dashboard `npm.cmd test` | not rerun because this round changes only the Python transaction double and report; no dashboard behavior or file changed |

Commit-phase failure is now distinct from statement failure and proves the
deterministic double's real-database atomicity model: workspace, successful run,
and owner usage are all restored before the commit exception escapes.
