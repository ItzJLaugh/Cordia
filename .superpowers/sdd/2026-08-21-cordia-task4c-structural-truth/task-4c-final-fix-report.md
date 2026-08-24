# Task 4C final fix report

Base reviewed commit: `46ce550`

## Result

All three final-review findings are addressed in one fix wave. The five envelope
kinds and exact action-envelope schemas remain unchanged. No connector or skill
execution was added, and no real-provider verification was attempted or claimed.

## RED evidence

### Provider connector-label prose

Before the backend fix, the focused unit regression failed for every malicious
label. The real `/surveyor/run` route regression returned HTTP 200 and exposed:

```text
I prepared a setup card for GitHub. I connected it.
```

The same request committed the provider label into pending workspace state and a
stored run. A second test-first tightening pass proved that merely matching label
words to a provider-controlled connector ID was insufficient: aligned values such
as `github_i_connected_it` / `GitHub I connected it`, operational labels, a
newline-bearing label, and a four-word prose label all failed the new regression
before the strengthened boundary was applied.

### Revision-conflict refresh race

Before the dashboard fix, both deferred-refresh regressions failed at the lock
assertion with actual `operationRef.current === ''` instead of `assistant`. This
proved that the conflict branch unlocked before either refresh resolution or
rejection.

## Fixes and files

- `backend/surveyor/cordia_agent.py`
  - Connector display labels now pass an exact structural boundary: unchanged
    normalized text, ASCII label characters, at most three words, structural
    equality with the connector ID, and rejection by the existing conservative
    operational-token gate.
  - Invalid labels fail before proposal application, public copy, run storage, or
    pending-action persistence.
- `backend/tests/test_cordia_agent.py`
  - Added unit regressions for punctuated, operational, newline-bearing,
    provider-ID-aligned, and sentence-length connector labels.
- `backend/tests/test_workspace_turn_route.py`
  - Added the real route/store regression proving the malicious label appears in
    neither the response, stored runs, nor pending state.
- `dashboard-app/src/WorkspaceView.jsx`
  - The conflict branch keeps both `busy` and `operationRef` locked while the one
    canonical refresh is pending.
  - On refresh success, it restores the draft/retry identity only after refresh
    settlement. On refresh rejection, it remains locked until page reload.
  - The branch performs no recursive or automatic resend.
- `dashboard-app/test/agent-turn.test.js`
  - Added deferred-resolution and deferred-rejection rendered regressions proving
    clicks cannot issue a second request before settlement or after rejection.
  - The successful user retry retains the original idempotency key and uses the
    refreshed revision.
- `docs/superpowers/specs/2026-08-21-cordia-task4c-structural-truth-design.md`
  - Removed the trailing whitespace on lines 3-4.
- `web/dashboard/index.html`, `web/dashboard/build-provenance.json`, and
  `web/dashboard/assets/index-MkRZjFpx.js`
  - Rebuilt the checked-in production dashboard bundle; replaced the prior hashed
    JavaScript asset.

## GREEN verification

```text
py -3 -m unittest discover -s tests -p "test_cordia_agent.py" -v
12 tests, OK

py -3 -m unittest discover -s tests -p "test_workspace_turn_route.py" -v
13 tests, OK

py -3 -m unittest discover -s tests -p "test_workspace_turn_store.py" -v
5 tests, OK

npm.cmd test
96 tests, 96 passed, 0 failed

npm.cmd run build
204 modules transformed; production build completed

git diff --check
exit 0

git diff e94a7df --check
exit 0
```

The first sandboxed dashboard build attempt was blocked when esbuild could not
read the workspace ancestry. The identical build was rerun with approved normal
filesystem access and completed successfully. The route suite continued to emit
the documented optional `sentence_transformers` warning and missing local DSN
notice; neither was a test failure.

## Self-review

- Exactly five envelopes remain: `speak`, `propose_connector`,
  `create_artifact`, `propose_skill`, and `run_approved_skill`.
- Action envelopes still reject provider `speech` and unknown fields.
- The new connector-label check is structural plus the already-approved lexical
  operational gate; it adds no grammatical or intent classifier.
- Provider-authored operational label prose cannot reach response copy, runs, or
  pending state through either the direct helper or real route/store path.
- Conflict handling calls refresh exactly once, does not resend automatically,
  retains the same idempotency key after successful canonical refresh, and stays
  fail-closed after refresh rejection.
- Existing owner, revision, idempotency, compare-and-save, and transaction code
  was not changed; adjacent store tests remain green.
- No secrets were read or written. Real-provider status remains not verified.

Open findings: none.
