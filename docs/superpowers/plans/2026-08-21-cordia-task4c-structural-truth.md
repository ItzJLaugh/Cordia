# Cordia Task 4C Structural Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace semantic regex policing with deterministic action copy, preserve current connector/runtime truth on every workspace creation path, and make revision-conflict retries safe.

**Architecture:** Keep the five existing Cordia Agent envelope kinds, but remove provider-controlled `speech` from all four action envelopes. Backend deterministic code creates public copy from validated action state; conversational `speak` uses a conservative operational-token redirect instead of grammatical truth inference. Existing locked PostgreSQL workspace projection and dashboard retry state are adapted in place.

**Tech Stack:** Python 3.12 standard library, PostgreSQL/psycopg2, Node test runner, React 18, Vite.

**Spec:** `docs/superpowers/specs/2026-08-21-cordia-task4c-structural-truth-design.md`

## Global Constraints

- The five kinds remain exactly `speak`, `propose_connector`, `create_artifact`, `propose_skill`, and `run_approved_skill`.
- Action envelopes do not accept provider-controlled `speech` or unknown fields.
- Task 4C performs no connector request and no skill execution.
- Only validated display labels may enter deterministic action copy.
- Operational `speak` vocabulary returns fixed clarification copy; it is not a successful action and is not persisted as provider prose.
- Every workspace creation path reads connector preference and runtime truth while holding the normalized-owner workspace-set transaction lock.
- Revision conflicts retain draft and idempotency key, refresh canonical state once, and never automatically call the model twice.
- Real-provider status remains **Not yet verified** unless an approved credential is exercised through the authenticated production route.
- The existing optional `sentence_transformers` baseline failure must be reported honestly and must not be called a full backend pass.

---

### Task 1: Deterministic Five-Envelope Public Copy

**Files:**
- Modify: `backend/surveyor/cordia_agent.py`
- Modify: `backend/tests/test_cordia_agent.py`
- Modify: `backend/tests/test_workspace_turn_route.py`
- Modify: `dashboard-app/src/workspace-view.js`
- Modify: `dashboard-app/test/agent-turn.test.js`

**Interfaces:**
- Consumes: `validate_envelope(value, known_connector_names=()) -> dict`, `apply_proposal(workspace, envelope) -> tuple[dict, dict]`.
- Produces: `public_action_copy(envelope: dict, action: dict | None) -> str`; action envelopes contain only `kind` and `proposal`; public route responses retain exact `{ok, speech, action, revision}`.

- [ ] **Step 1: Write backend RED tests for exact action schemas and deterministic copy**

Add this table to `backend/tests/test_cordia_agent.py`:

```python
def test_action_envelopes_reject_provider_speech_and_use_fixed_copy(self):
    cases = (
        ({"kind": "propose_connector", "proposal": {
            "connector_id": "google_drive", "display_name": "Google Drive",
            "setup_kind": "api_key", "purpose": "Read selected files."}},
         "I prepared a setup card for Google Drive."),
        ({"kind": "create_artifact", "proposal": {
            "artifact_id": "drive_summary", "title": "Drive summary",
            "view_mode": "list", "summary": "Selected files."}},
         "I prepared a proposed workspace artifact."),
        ({"kind": "propose_skill", "proposal": {
            "skill_id": "review_drive", "name": "Review Drive",
            "purpose": "Review selected files.", "connector_id": "google_drive",
            "operation_id": "list_files", "artifact_id": "drive_summary"}},
         "I prepared a proposed skill for review."),
        ({"kind": "run_approved_skill", "proposal": {"skill_id": "review_drive"}},
         "This skill requires approval before it can run."),
    )
    for envelope, copy in cases:
        accepted = cordia_agent.validate_envelope(envelope)
        workspace, result = cordia_agent.apply_proposal(BASE_WORKSPACE, accepted)
        self.assertEqual(result["speech"], copy)
        self.assertNotIn("speech", accepted)
        with self.assertRaises(ValueError):
            cordia_agent.validate_envelope({**envelope, "speech": "I deployed it."})
```

- [ ] **Step 2: Write backend RED tests for structural operational-speech recovery**

```python
def test_operational_speak_returns_fixed_clarification_without_provider_prose(self):
    variants = (
        "GitHub is live.",
        "I have not configured GitHub.",
        "If GitHub is connected, can we proceed?",
        "I would have configured GitHub if approved.",
        "This feature is available in the catalog, and the app is ready.",
    )
    for speech in variants:
        accepted = cordia_agent.validate_envelope({"kind": "speak", "speech": speech})
        self.assertEqual(accepted, {"kind": "speak", "speech":
            "I can discuss that, but workspace status and changes must use a Cordia action."})
    ordinary = cordia_agent.validate_envelope({"kind": "speak",
                                                "speech": "What outcome matters most?"})
    self.assertEqual(ordinary["speech"], "What outcome matters most?")
```

The token matcher must lowercase Unicode-normalized word tokens and reject the
families listed in Global Constraints without parsing clauses, polarity, or
grammar. It must apply after privacy screening and before persistence.

- [ ] **Step 3: Run backend tests to confirm RED**

Run:

```powershell
Set-Location backend
py -3 -m unittest discover -s tests -p "test_cordia_agent.py" -v
py -3 -m unittest discover -s tests -p "test_workspace_turn_route.py" -v
```

Expected: failures because action envelopes still require `speech`, and operational `speak` currently uses semantic classification.

- [ ] **Step 4: Implement exact schemas, token recovery, and deterministic copy**

Replace the action-field map and semantic classifier in `cordia_agent.py` with:

```python
_ACTION_FIELDS = {
    "speak": {"kind", "speech"},
    "propose_connector": {"kind", "proposal"},
    "create_artifact": {"kind", "proposal"},
    "propose_skill": {"kind", "proposal"},
    "run_approved_skill": {"kind", "proposal"},
}
_OPERATIONAL_TOKEN = re.compile(
    r"\b(?:connect\w*|configur\w*|setup|setups|run|runs|running|ran|execut\w*|"
    r"deploy\w*|creat\w*|approv\w*|complet\w*|live|enabled|active|ready|available)\b",
    re.IGNORECASE,
)
_OPERATIONAL_CLARIFICATION = (
    "I can discuss that, but workspace status and changes must use a Cordia action."
)

def public_action_copy(envelope: dict, action: dict | None) -> str:
    kind = envelope["kind"]
    if kind == "propose_connector":
        return f"I prepared a setup card for {envelope['proposal']['display_name']}."
    if kind == "create_artifact":
        return "I prepared a proposed workspace artifact."
    if kind == "propose_skill":
        return "I prepared a proposed skill for review."
    if kind == "run_approved_skill":
        return "This skill requires approval before it can run."
    return envelope["speech"]
```

`validate_envelope()` must transform only operational `speak` text to
`_OPERATIONAL_CLARIFICATION`. It must reject `speech` on every action kind.
`apply_proposal()` must call `public_action_copy()` after deterministic action
state is known and store/return only that copy.

- [ ] **Step 5: Update system-prompt schemas and route tests**

Assert the generated schema lists `speech` only for `speak`. Route tests must use
provider action envelopes without `speech` and assert that runs/API output contain
only fixed copy, not sentinel provider prose:

```python
self.model_output = json.dumps({"kind": "propose_connector", "proposal": {
    "connector_id": "google_drive", "display_name": "Google Drive",
    "setup_kind": "api_key", "purpose": "Read selected files."}})
response, status = self.post_turn()
self.assertEqual(status, 200)
self.assertEqual(response["speech"], "I prepared a setup card for Google Drive.")
self.assertNotIn("sentinel-provider-prose", repr(response) + repr(self.store.runs))
```

- [ ] **Step 6: Update dashboard contract tests**

In `dashboard-app/test/agent-turn.test.js`, prove the dashboard accepts fixed
server copy and rejects extra provider fields:

```javascript
assert.equal(agentTurnModel({ok:true, revision:2,
  speech:'I prepared a setup card for Google Drive.',
  action:{kind:'propose_connector', state:'setup_required',
          connector_id:'google_drive', setup_kind:'api_key'}}).text,
  'I prepared a setup card for Google Drive.')
assert.equal(agentTurnModel({ok:true, revision:2, speech:'safe', providerSpeech:'unsafe', action:null}), null)
```

- [ ] **Step 7: Run focused and adjacent tests**

Run:

```powershell
Set-Location backend
py -3 -m unittest discover -s tests -p "test_cordia_agent.py" -v
py -3 -m unittest discover -s tests -p "test_workspace_turn_route.py" -v
py -3 -m unittest discover -s tests -p "test_workspace_turn_store.py" -v
Set-Location ..\dashboard-app
npm.cmd test
```

Expected: all discovered tests pass; no test accepts provider action prose.

- [ ] **Step 8: Commit Task 1**

```powershell
git add backend/surveyor/cordia_agent.py backend/tests/test_cordia_agent.py backend/tests/test_workspace_turn_route.py dashboard-app/src/workspace-view.js dashboard-app/test/agent-turn.test.js
git commit -m "fix: make Cordia action copy deterministic"
```

---

### Task 2: Current Connector Runtime on Every Workspace Creation

**Files:**
- Modify: `backend/surveyor/store.py`
- Modify: `backend/tests/test_workspace_turn_store.py`
- Modify: `backend/tests/test_profile_calibration_atomic.py`
- Modify: `backend/tests/test_workspace_generation.py`

**Interfaces:**
- Consumes: `_lock_owner_workspace_set(cursor, email)`, `_workspace_from_current_connectors(cursor, email, workspace_id, definition, include_runtime=True)`.
- Produces: every persisted new workspace is projected from connector preference and observed runtime truth read under the same owner-set lock.

- [ ] **Step 1: Write RED tests for initial and calibration runtime inheritance**

Add fixtures with an existing archived workspace whose GitHub connector has
`runtime_status: "needs_attention"`, then create a new initial/calibrated
workspace and assert:

```python
created = self.store.created_workspace
github = next(item for item in created["connectors"] if item["id"] == "github")
self.assertEqual(github["runtime_status"], "needs_attention")
```

Add the same assertion for `runtime_status: "live"`. Assert source artifacts,
title, description, memory, and pending actions remain unchanged by connector
projection.

- [ ] **Step 2: Run creation tests to confirm RED**

Run:

```powershell
Set-Location backend
py -3 -m unittest discover -s tests -p "test_profile_calibration_atomic.py" -v
py -3 -m unittest discover -s tests -p "test_workspace_generation.py" -v
py -3 -m unittest discover -s tests -p "test_workspace_turn_store.py" -v
```

Expected: initial/calibration tests fail because `_prepared_with_current_connectors()` passes `include_runtime=False`.

- [ ] **Step 3: Enable locked runtime reconciliation for every creation helper**

Change `_prepared_with_current_connectors()` to call:

```python
return {**prepared, "workspace": _workspace_from_current_connectors(
    cursor, email, prepared["id"], definition, include_runtime=True)}
```

Search all `_workspace_from_current_connectors` calls and require either the
default `True` or explicit `include_runtime=True`. Remove the false option if no
caller requires it. Connector preference/runtime reads remain after
`_lock_owner_workspace_set()` in the same database transaction.

- [ ] **Step 4: Run store and generation tests**

Run the three commands from Step 2 again.

Expected: all pass; stale candidates inherit current runtime truth while keeping
non-connector state.

- [ ] **Step 5: Commit Task 2**

```powershell
git add backend/surveyor/store.py backend/tests/test_workspace_turn_store.py backend/tests/test_profile_calibration_atomic.py backend/tests/test_workspace_generation.py
git commit -m "fix: inherit connector runtime on workspace creation"
```

---

### Task 3: Revision-Conflict Refresh and Retry Identity

**Files:**
- Modify: `dashboard-app/src/api.js`
- Modify: `dashboard-app/src/WorkspaceView.jsx`
- Modify: `dashboard-app/src/workspace-view.js`
- Modify: `dashboard-app/test/api.test.js`
- Modify: `dashboard-app/test/agent-turn.test.js`

**Interfaces:**
- Consumes: `postRun(id, revision, message, idempotencyKey)`, `refresh()`, `assistantTurnFailed(state, note, preserveRetry)`.
- Produces: `assistantRevisionConflict(state, note) -> state`; one canonical refresh on 409; retained draft/idempotency key; no automatic resend.

- [ ] **Step 1: Write RED state-model tests**

```javascript
const failed = assistantRevisionConflict({
  transcript:[{id:'pending-1', who:'you', text:'Connect Drive'}],
  draft:'', note:'', busy:true,
  pending:{id:'pending-1', text:'Connect Drive', idempotencyKey:'turn-fixed'},
}, 'Workspace changed. Review it and retry.')
assert.equal(failed.draft, 'Connect Drive')
assert.deepEqual(failed.retry, {text:'Connect Drive', idempotencyKey:'turn-fixed'})
assert.equal(failed.busy, false)
```

- [ ] **Step 2: Write rendered/controller RED test for 409 recovery**

Mock the first `postRun` as a 409 `revision_conflict`, `refresh()` as updating
the parent revision from 4 to 5, and the second click as success. Assert:

```javascript
assert.equal(refreshCalls, 1)
assert.deepEqual(postCalls.map(call => call.idempotencyKey), ['turn-fixed', 'turn-fixed'])
assert.deepEqual(postCalls.map(call => call.revision), [4, 5])
assert.equal(postCalls.length, 2) // two user clicks, never an automatic resend
```

- [ ] **Step 3: Run dashboard tests to confirm RED**

Run:

```powershell
Set-Location dashboard-app
npm.cmd test
```

Expected: conflict path does not refresh and the next send receives a new key.

- [ ] **Step 4: Implement explicit 409 classification and refresh flow**

Ensure `apiErrorKind(error)` returns `revision-conflict` only for the exact
bounded backend conflict response. Add:

```javascript
export function assistantRevisionConflict(state, note) {
  return assistantTurnFailed(state, note, true)
}
```

In `Assistant.send().catch`, handle it before generic definitive errors:

```javascript
if (kind === 'revision-conflict') {
  operationRef.current = ''
  setState((current) => assistantRevisionConflict(
    current, 'Workspace changed. Review the refreshed workspace and retry.'))
  try { await refresh() } catch (_refreshError) {
    if (aliveRef.current) setState((current) => ({...current,
      note:'Workspace refresh failed. Reload before retrying.'}))
  }
  return
}
```

This branch never calls `send()` recursively. The parent canonical refresh must
provide the new `workspaceRevision` before the user can retry.

- [ ] **Step 5: Preserve malformed-success and transport retry behavior**

Retain the existing exact idempotency key for malformed `200 {ok:true}` and
ambiguous network/5xx responses. Add a test proving a user edit that materially
changes the trimmed draft creates a new key, while unchanged text reuses it.

- [ ] **Step 6: Run the full dashboard suite**

Run:

```powershell
Set-Location dashboard-app
npm.cmd test
npm.cmd run build
```

Expected: tests pass and Vite creates the production bundle. If the sandbox
blocks esbuild filesystem access, rerun the identical build with approved normal
access; do not claim a build from a blocked run.

- [ ] **Step 7: Commit Task 3**

```powershell
git add dashboard-app/src/api.js dashboard-app/src/WorkspaceView.jsx dashboard-app/src/workspace-view.js dashboard-app/test/api.test.js dashboard-app/test/agent-turn.test.js web/dashboard
git commit -m "fix: refresh Cordia revision conflicts safely"
```

---

### Task 4: Integrated Task 4C Verification and Evidence Boundary

**Files:**
- Modify: `docs/evidence/cordia-thin-spine-real-provider.md`
- Modify: `.superpowers/sdd/2026-08-20-cordia-thin-spine/progress.md` (ignored local ledger only)
- Test: `backend/tests/test_cordia_agent.py`
- Test: `backend/tests/test_workspace_turn_route.py`
- Test: `backend/tests/test_workspace_turn_store.py`
- Test: `dashboard-app/test/agent-turn.test.js`

**Interfaces:**
- Consumes: completed Tasks 1-3.
- Produces: a reviewed local Task 4C result with live-provider status stated exactly as observed.

- [ ] **Step 1: Run focused backend integration suites**

```powershell
Set-Location backend
py -3 -m unittest discover -s tests -p "test_cordia_agent.py" -v
py -3 -m unittest discover -s tests -p "test_workspace_turn_route.py" -v
py -3 -m unittest discover -s tests -p "test_workspace_turn_store.py" -v
py -3 -m unittest discover -s tests -p "test_profile_calibration_atomic.py" -v
py -3 -m unittest discover -s tests -p "test_workspace_generation.py" -v
```

Expected: all discovered focused tests pass.

- [ ] **Step 2: Run dashboard and full backend comparisons**

```powershell
Set-Location ..\dashboard-app
npm.cmd test
Set-Location ..\backend
py -3 -m unittest discover -s tests -v
```

Expected: dashboard passes. Backend must be compared to the recorded baseline;
the optional `sentence_transformers` import failure may remain but must be the
only failure before proceeding.

- [ ] **Step 3: Verify privacy and obsolete semantic code removal**

```powershell
Set-Location ..
rg -n "_false_speak_claim|_AGENT_COMPLETION|_BACKEND_STATE|_AGENT_NEGATION|_AGENT_MODAL" backend/surveyor/cordia_agent.py
rg -n "sentinel-provider-prose|sk-|ghp_|github_pat_|AKIA|BEGIN PRIVATE KEY" web/dashboard docs/evidence
git diff --check
```

Expected: obsolete semantic classifier search returns no matches; secret/token
sentinels are absent from release assets/evidence; diff check exits zero.

- [ ] **Step 4: Record the real-provider evidence boundary**

If approved `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_KEY` are not present, keep:

```markdown
Status: Not yet verified with a real provider.
Reason: No approved production credential was available during Task 4C verification.
```

Do not call a provider and do not write a fabricated timestamp. If credentials
are present through the approved secret channel, follow the parent plan's safe
authenticated route gate and record only timestamp, model identifier, HTTP
status, envelope kind, and revision—never prompt, response prose, or key.

- [ ] **Step 5: Commit verification evidence if changed**

```powershell
git add docs/evidence/cordia-thin-spine-real-provider.md
git diff --cached --quiet || git commit -m "docs: record Task 4C verification boundary"
```

- [ ] **Step 6: Request independent whole-Task-4 review**

Review cumulative Task 4 from `e94a7df` through the final Task 4C commit. The
reviewer must verify deterministic action copy, conservative conversational
recovery, connector/runtime creation truth, conflict retry identity, all prior
owner/transaction/idempotency boundaries, and no connector execution. Task 5
cannot begin with any open Critical or Important finding.
