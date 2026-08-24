# Cordia MVP Sprint 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish Cordia's existing kernel, provide managed OpenAI-backed workspace turns, and enforce ten successful free turns without adding a second architecture.

**Architecture:** Reuse `model_provider.call`, the five-envelope `cordia_agent`, owner-scoped PostgreSQL workspace persistence, and `/surveyor/run`. Add only a durable owner usage row, safe provider status, and an integration contract that labels deterministic doubles as simulated. Universal connectors, generated skills, and desktop packaging receive separate later plans.

**Tech Stack:** Python 3.12 standard library, PostgreSQL/psycopg2, Node test runner, React 18, Vite, systemd/Apache deployment.

**Spec:** `docs/CORDIA_MVP_FRAMEWORK.md`

## Global Constraints

- Complete `docs/superpowers/plans/2026-08-21-cordia-task4c-structural-truth.md` before this plan changes production code.
- Reuse the existing model, agent, workspace, store, and HTTP composition paths; do not add a gateway, framework, queue, or second state owner.
- The beta provider is OpenAI configured server-side through `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_KEY`; no key may enter source, browser code, the desktop executable, logs, evidence, prompts, or responses.
- The model returns exactly one of the existing five Cordia actions.
- A free owner receives ten successfully committed model-backed turns across all workspaces.
- Missing configuration, provider failure, validation failure, revision conflict, duplicate replay, and failed commit do not consume a turn.
- A duplicate idempotency key returns its prior result even after the owner reaches the limit.
- Tests using doubles are labeled simulated. Only an observed approved credential through the authenticated route may be labeled verified locally or verified live.
- The known optional `sentence_transformers` import failure is reported honestly and is never called a full backend pass.

---

### Task 1: Executable Framework Contract

**Files:**
- Create: `backend/tests/test_mvp_framework.py`
- Modify: `docs/CORDIA_MVP_FRAMEWORK.md`

**Interfaces:**
- Consumes: `cordia_agent.build_context(memory, workspace, recent)`, `cordia_agent.run_turn(context, message, call_model)`, `cordia_agent.apply_proposal(workspace, envelope)`.
- Produces: one deterministic simulated proof that the existing kernel carries memory through a validated action into a revised workspace.

- [ ] **Step 1: Write the framework contract test**

Create a test that uses the real production functions and only replaces the external model call:

```python
def test_simulated_kernel_carries_memory_action_and_revision(self):
    workspace = {
        "id": "workspace_demo", "revision": 0,
        "title": "Demo", "description": "",
        "connectors": [], "artifacts": [], "skills": [],
        "pending_actions": [],
    }
    seen = {}
    def simulated_model(system, user, max_tokens):
        seen.update(system=system, user=user, max_tokens=max_tokens)
        return json.dumps({"kind": "propose_connector", "proposal": {
            "connector_id": "status_api", "display_name": "Status API",
            "setup_kind": "api_key", "purpose": "Read service status."}})
    context = cordia_agent.build_context(
        "# Workspace Memory\n\n## Communication policy\n- Start with the outcome.",
        workspace, [])
    envelope = cordia_agent.run_turn(context, "Connect our status API", simulated_model)
    updated, public = cordia_agent.apply_proposal(workspace, envelope)
    self.assertIn("Start with the outcome", seen["system"])
    self.assertEqual(public["speech"], "I prepared a connector setup card.")
    self.assertEqual(public["revision"], 1)
    self.assertEqual(updated["pending_actions"][0]["kind"], "propose_connector")
```

- [ ] **Step 2: Run the test and record its observed baseline**

Run from `backend`:

```powershell
py -3 -m unittest discover -s tests -p "test_mvp_framework.py" -v
```

If it passes without production changes, record that as reuse evidence rather than fabricating RED. If it exposes a missing contract, capture the exact RED and patch only the existing production function responsible.

- [ ] **Step 3: Add the framework disposition table**

Append a table to `docs/CORDIA_MVP_FRAMEWORK.md` mapping each contract to its existing owner:

```markdown
| Contract | Existing owner | Sprint 1 action |
| Workspace | `workspace_state.py` and `store.py` | reuse |
| Model provider | `model_provider.py` | configure and verify |
| Agent action | `cordia_agent.py` | reuse after Task 4C |
| Connector | `connector_runtime.py` | defer execution to Sprint 2 |
| Artifact | `workspace_state.py` renderer projection | defer real result to Sprint 3 |
| Skill | `skills.py` and capability gateway | defer generated execution to Sprint 3 |
```

- [ ] **Step 4: Run adjacent agent tests**

```powershell
py -3 -m unittest discover -s tests -p "test_cordia_agent.py" -v
py -3 -m unittest discover -s tests -p "test_workspace_turn_route.py" -v
git diff --check
```

- [ ] **Step 5: Commit**

```powershell
git add backend/tests/test_mvp_framework.py docs/CORDIA_MVP_FRAMEWORK.md
git commit -m "test: prove the Cordia MVP kernel path"
```

---

### Task 2: Safe Managed OpenAI Configuration

**Files:**
- Modify: `backend/surveyor/model_provider.py`
- Modify: `backend/tests/test_model_provider.py`
- Modify: `backend/surveyor/preflight.py`
- Modify: `backend/tests/test_preflight.py`
- Modify: `backend/SURVEYOR_RUNTIME_SETUP.md`

**Interfaces:**
- Consumes: existing `model_provider.call(system: str, user: str, max_tokens: int = 900, opener=...) -> str`.
- Produces: `model_provider.status() -> dict` returning only `{"provider":"openai","configured":bool,"model":str}` and preflight readiness based on the same configuration parser.

- [ ] **Step 1: Write RED status and secret-boundary tests**

```python
def test_status_is_safe_and_uses_the_same_configuration(self):
    with configured_provider(LLM_MODEL="gpt-cordia"):
        self.assertEqual(model_provider.status(), {
            "provider": "openai", "configured": True, "model": "gpt-cordia"})
    self.assertNotIn("test-secret", repr(model_provider.status))

def test_status_is_unconfigured_without_network_or_secret_echo(self):
    with patch.dict(os.environ, {}, clear=True):
        self.assertEqual(model_provider.status(), {
            "provider": "openai", "configured": False, "model": ""})
```

Add preflight tests proving that missing variables produce a named not-ready
check and configured variables produce ready without contacting OpenAI.

- [ ] **Step 2: Run focused tests to verify RED**

```powershell
py -3 -m unittest discover -s tests -p "test_model_provider.py" -v
py -3 -m unittest discover -s tests -p "test_preflight.py" -v
```

Expected: `status` is missing and preflight does not expose the unified provider check.

- [ ] **Step 3: Implement status without another provider abstraction**

Use `configuration()` as the only parser:

```python
def status() -> dict:
    try:
        config = configuration()
    except ModelUnavailable:
        return {"provider": "openai", "configured": False, "model": ""}
    return {"provider": "openai", "configured": True,
            "model": str(config["model"])[:120]}
```

Preflight calls `status()` and reports only provider/configured/model. It never
calls `call()` and never includes the key or base URL.

- [ ] **Step 4: Document exact VPS configuration**

Document these environment names without values:

```text
LLM_BASE_URL=https://api.openai.com/v1/chat/completions
LLM_MODEL=<approved OpenAI model identifier>
LLM_KEY=<stored only in /etc/cordia/cordia.env>
```

State explicitly that ChatGPT subscriptions do not supply this API credential
and that no real-provider claim exists until Task 4's authenticated observation.

- [ ] **Step 5: Run focused tests and commit**

```powershell
py -3 -m unittest discover -s tests -p "test_model_provider.py" -v
py -3 -m unittest discover -s tests -p "test_preflight.py" -v
git diff --check
git add backend/surveyor/model_provider.py backend/tests/test_model_provider.py backend/surveyor/preflight.py backend/tests/test_preflight.py backend/SURVEYOR_RUNTIME_SETUP.md
git commit -m "feat: expose safe OpenAI provider readiness"
```

---

### Task 3: Ten Successful Free Turns

**Files:**
- Modify: `backend/surveyor/store.py`
- Modify: `backend/training_backend.py`
- Modify: `backend/tests/test_workspace_turn_store.py`
- Modify: `backend/tests/test_workspace_turn_route.py`
- Modify: `dashboard-app/src/api.js`
- Modify: `dashboard-app/src/workspace-view.js`
- Modify: `dashboard-app/test/api.test.js`
- Modify: `dashboard-app/test/agent-turn.test.js`

**Interfaces:**
- Produces: `store.workspace_turn_usage(email: str) -> {"used": int, "limit": 10}`.
- Extends: `commit_workspace_turn(...)` with status `limit` when no successful allowance remains.
- Produces fixed limit response: `{"ok":false,"error":"Free agent actions used. Upgrade to continue.","code":"usage_limit","used":10,"limit":10}` with HTTP 402.

- [ ] **Step 1: Write store RED tests**

Before changing `SCHEMA`, write tests proving:

- turns 1 through 10 commit and increment exactly once;
- turn 11 returns `status=limit` without workspace or run mutation;
- a duplicate key returns `prior` before the limit check;
- missing/conflict/provider failure paths do not increment;
- two workspaces share the same owner allowance; and
- another owner has an independent allowance.

- [ ] **Step 2: Run store tests to verify RED**

```powershell
py -3 -m unittest discover -s tests -p "test_workspace_turn_store.py" -v
```

Expected: missing schema/query behavior and no `limit` result.

- [ ] **Step 3: Implement the atomic commit check**

Add the exact durable owner counter to `SCHEMA`:

```sql
CREATE TABLE IF NOT EXISTS surveyor_usage(
    email TEXT PRIMARY KEY,
    successful_turns INTEGER NOT NULL DEFAULT 0 CHECK(successful_turns >= 0),
    updated TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
```

Inside the existing `commit_workspace_turn` transaction:

1. lock the owner workspace;
2. return a prior idempotent result if present;
3. validate expected revision;
4. insert the owner's usage row with `ON CONFLICT DO NOTHING`;
5. select that usage row `FOR UPDATE`;
6. return `{"status":"limit","usage":{"used":10,"limit":10}}` when used is 10;
7. update workspace, insert the successful run, and increment usage once.

`workspace_turn_usage()` returns bounded integers and never creates model work.

- [ ] **Step 4: Write route and dashboard RED tests**

Route tests prove an owner already at 10 is rejected before the model callback,
while a duplicate prior result is returned. Dashboard tests classify only the
exact 402/code/used/limit shape as `usage-limit`, preserve workspace state, and
display the fixed error. Unknown 402 bodies fail closed as generic errors.

- [ ] **Step 5: Implement route precheck and commit result**

After the prior-idempotency check and before context/model work:

```python
usage = surveyor.store.workspace_turn_usage(email)
if usage["used"] >= usage["limit"]:
    self._json({"ok": False,
                "error": "Free agent actions used. Upgrade to continue.",
                "code": "usage_limit", **usage}, 402)
    return
```

Handle a transactional `commit["status"] == "limit"` with the identical fixed
response. The second check closes concurrent commit races; it may reject a
concurrently exhausted call but never records or charges it as successful.

- [ ] **Step 6: Run focused and dashboard suites**

```powershell
py -3 -m unittest discover -s tests -p "test_workspace_turn_store.py" -v
py -3 -m unittest discover -s tests -p "test_workspace_turn_route.py" -v
Set-Location ..\dashboard-app
npm.cmd test
git diff --check
```

- [ ] **Step 7: Commit**

```powershell
git add backend/surveyor/store.py backend/training_backend.py backend/tests/test_workspace_turn_store.py backend/tests/test_workspace_turn_route.py dashboard-app/src/api.js dashboard-app/src/workspace-view.js dashboard-app/test/api.test.js dashboard-app/test/agent-turn.test.js
git commit -m "feat: enforce ten free Cordia Agent turns"
```

---

### Task 4: Real Authenticated Provider Proof

**Files:**
- Create: `docs/evidence/cordia-mvp-openai.md`
- Create: `docs/LIVE_SETUP_AND_TEST_MANUAL.md`
- Test: `backend/tests/test_mvp_framework.py`
- Test: `backend/tests/test_workspace_turn_route.py`
- Test: `dashboard-app/test/agent-turn.test.js`

**Interfaces:**
- Consumes: configured server provider, authenticated account, calibrated canonical workspace, and `/surveyor/run`.
- Produces: bounded evidence containing only commit SHA, UTC timestamp, model identifier, HTTP status, accepted envelope kind, workspace revision, and remaining allowance.

- [ ] **Step 1: Run local deterministic comparisons**

```powershell
Set-Location backend
py -3 -m unittest discover -s tests -p "test_mvp_framework.py" -v
py -3 -m unittest discover -s tests -p "test_model_provider.py" -v
py -3 -m unittest discover -s tests -p "test_workspace_turn_route.py" -v
py -3 -m unittest discover -s tests -p "test_workspace_turn_store.py" -v
Set-Location ..\dashboard-app
npm.cmd test
npm.cmd run build
```

Record these as implemented/simulated evidence only.

- [ ] **Step 2: Run the complete backend comparison**

```powershell
Set-Location ..\backend
py -3 -m unittest discover -s tests -v
```

Compare against the recorded baseline. The optional `sentence_transformers`
failure may remain the only failure and must be named exactly.

- [ ] **Step 3: Stop at the credential boundary if unavailable**

When no approved VPS `LLM_KEY` exists, write exactly:

```markdown
Status: Not yet verified with OpenAI.
Reason: No approved server-side OpenAI credential was available.
```

Do not simulate this step and do not ask for a key in chat.

- [ ] **Step 4: Observe the authenticated route when configured**

Using a test account and the actual application UI/API session:

1. load the calibrated workspace;
2. submit `What outcome should we work on first?` once with a new idempotency key;
3. confirm a non-placeholder response and one accepted envelope;
4. reload and confirm the same persisted turn/revision;
5. resend the same idempotency key and confirm no additional provider call or usage increment;
6. confirm no key, prompt, full provider response, local path, or credential appears in logs or evidence.

- [ ] **Step 5: Write bounded evidence and manual**

Evidence contains no provider prose. The manual gives the human the sign-in,
survey, workspace-message, reload, usage-limit, and failure-recovery steps.

- [ ] **Step 6: Commit evidence and request whole-Sprint review**

```powershell
git add docs/evidence/cordia-mvp-openai.md docs/LIVE_SETUP_AND_TEST_MANUAL.md web/dashboard
git diff --cached --check
git commit -m "docs: record Cordia managed OpenAI evidence"
```

Independent review must verify the complete Sprint 1 diff, the truthful evidence
labels, no secret exposure, and no duplicate provider/state system. Sprint 2 may
start only with no open Critical or Important finding.
