# Cordia Beta Release 1: Intake and Cloud Continuity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the verified-account → bounded Surveyor → non-scored assessment → Cordia-Agent-generated canonical workspace → logout/login recovery path work as one honest beta journey.

**Architecture:** Keep the existing Postgres Surveyor profile, artifacts, interface compatibility records, canonical workspace state, and React workspace as the only owners. Bound intake to twelve user turns, add an idempotent authenticated workspace-generation operation driven entirely by the Surveyor profile and compiled artifacts, and make the operator assessment call that operation instead of sending new users into the legacy manual builder.

**Tech Stack:** Python 3.12 standard library, PostgreSQL/psycopg2, vanilla browser JavaScript with Node's built-in test runner, existing React/Vite workspace, existing Electron shell.

**Spec:** `docs/superpowers/specs/2026-08-18-cordia-beta-mvp-design.md`

## Global Constraints

- The Cordia Agent is the FDE and owns the user-facing transition from understanding to workspace generation.
- `docs/CORDIA_BUILD_CONTEXT.md`, `docs/WORKSPACE_FDE_PIVOT_CONTEXT.md`, and the approved beta spec are product authority.
- Surveyor is non-scored and separate from CordiaAIE certification/course logic.
- The beta Surveyor intake uses at most 12 user turns: 6 preference prompts, 3 scenario prompts, and 3 freeform prompts.
- Partial or malformed extraction never discards previously saved profile evidence.
- `surveyor_interfaces` remains the compatibility/runtime definition record; `surveyor_workspaces` remains the canonical rendered state.
- Workspace generation must be authenticated, owner-scoped, idempotent per account, and atomic for a newly generated workspace.
- The initial workspace title is the fixed safe value `My Workspace`; user-authored profile text does not become a workspace identifier or title.
- The existing legacy `web/assessment.html` remains CordiaAIE certification-specific and must not be linked from Surveyor.
- The existing `web/builder.html` may remain as an advanced compatibility editor, but it is not the primary new-user path.
- Unknown request fields, unsafe identifiers, credential-shaped values, local paths, and malformed response shapes fail closed.
- No connector, billing, Desktop packaging, or Alidora execution scope is added in Release 1.
- Every task uses RED → GREEN tests and ends in its own commit.

---

## File Structure

### New files

- `backend/surveyor/workspace_generation.py` — pure profile/artifact-to-definition and canonical-state preparation.
- `backend/tests/test_surveyor_onboarding.py` — deterministic 12-turn sequencing, completion, resume, and malformed-answer behavior.
- `backend/tests/test_workspace_generation.py` — pure generation, store transaction, route ownership/idempotency, and privacy tests.
- `backend/tests/test_beta_intake_journey.py` — real pipeline-to-generation-to-recovery integration contract.
- `web/assets/cordia-surveyor-flow.js` — fail-closed browser projection of Surveyor progress and completion actions.
- `web/assets/cordia-workspace-generation.js` — fixed authenticated workspace-generation request and safe navigation coordinator.
- `web/test/surveyor_flow.test.js` — Surveyor progress, action, draft recovery, and CordiaAIE-separation tests.
- `web/test/workspace_generation.test.js` — generation response, duplicate click, error recovery, and navigation tests.
- `web/test/beta_intake_journey.test.js` — browser-level assessment → generated workspace → auth resume continuity test.

### Modified files

- `backend/surveyor/types.py` — named beta onboarding limits and completion contract.
- `backend/surveyor/question_strategy.py` — stage-attempt bookkeeping and bounded next-step selection.
- `backend/surveyor/operator_profile.py` — use the bounded onboarding completion contract.
- `backend/surveyor/pipeline.py` — return bounded onboarding progress with conversation responses.
- `backend/surveyor/store.py` — atomic, advisory-lock-protected initial workspace persistence.
- `backend/surveyor/__init__.py` — export `workspace_generation`.
- `backend/training_backend.py` — fixed `POST /surveyor/workspace/generate` route.
- `web/assets/cordia-surveyor.js` — use safe progress model, remove certification/build shortcuts, and preserve failed drafts.
- `web/assets/operator-profile.js` — represent new-workspace creation as a fixed `generate` action, never a server URL.
- `web/profile.html` — render and execute the fixed generation action.
- `web/test/operator_profile.test.js` — update the primary action contract without weakening privacy assertions.
- `backend/surveyor/README.md` — document the Release 1 journey and remaining boundaries.
- `docs/TODO_CORDIA_VERTICAL_SLICE.md` — check only directly proven Release 1 items.

---

### Task 1: Bound Surveyor onboarding to twelve user turns

**Files:**
- Create: `backend/tests/test_surveyor_onboarding.py`
- Modify: `backend/surveyor/types.py`
- Modify: `backend/surveyor/question_strategy.py`
- Modify: `backend/surveyor/operator_profile.py`
- Modify: `backend/surveyor/pipeline.py`

**Interfaces:**
- Produces `types.ONBOARDING_TURN_LIMIT: int = 12`.
- Produces `types.ONBOARDING_PREFERENCE_LIMIT: int = 6`.
- Produces `types.ONBOARDING_SCENARIO_LIMIT: int = 3`.
- Produces `types.ONBOARDING_FREEFORM_LIMIT: int = 3`.
- Produces `types.onboarding_complete(profile: dict) -> bool`.
- Produces `question_strategy.attempted_keys(history: list, stage: str) -> list[str]`.
- Produces `question_strategy.next_step(profile: dict, history: list | None = None) -> dict`.
- Produces `pipeline.onboarding_status(profile: dict) -> dict` returning exactly `turn_limit`, `turns_used`, `turns_remaining`, and `complete`.
- Changes `pipeline.start()` and `pipeline.turn()` to return that status under `onboarding`.

- [ ] **Step 1: Write the failing bounded-onboarding tests**

Add tests that build message history using the exact `meta.stage` and `meta.key` fields already stored by `pipeline.turn()`:

```python
def stage_attempt(stage, key, answer):
    return [
        {"role": "assistant", "content": f"question-{key}",
         "meta": {"stage": stage, "key": key,
                  "signal": key if stage == "preferences" else None}},
        {"role": "user", "content": answer, "meta": {}},
    ]


def preference_history(count):
    history = []
    for index, key in enumerate(types.SIGNAL_PRIORITY[:count]):
        history.extend(stage_attempt("preferences", key, f"answer-{index}"))
    return history


class TestBoundedOnboarding(unittest.TestCase):
    def test_sequence_uses_six_preferences_three_scenarios_three_freeform_turns(self):
        profile = types.empty_profile()
        history = []
        stages = []
        for turn in range(types.ONBOARDING_TURN_LIMIT):
            step = question_strategy.next_step(profile, history)
            stages.append(step["stage"])
            history.extend([
                {"role": "assistant", "content": step["text"],
                 "meta": {"stage": step["stage"], "key": step["key"],
                          "signal": step["key"] if step["stage"] == "preferences" else None}},
                {"role": "user", "content": f"answer-{turn}", "meta": {}},
            ])
            profile["questions_answered"] = turn + 1
        self.assertEqual(stages, ["preferences"] * 6 + ["scenarios"] * 3 + ["freeform"] * 3)
        self.assertEqual(question_strategy.next_step(profile, history)["stage"], "done")

    def test_invalid_typed_scenario_attempt_moves_forward_without_inventing_a_choice(self):
        profile = types.empty_profile()
        history = preference_history(6) + stage_attempt("scenarios", scenarios.IDS[0], "typed answer")
        step = question_strategy.next_step(profile, history)
        self.assertEqual(step["stage"], "scenarios")
        self.assertEqual(step["key"], scenarios.IDS[1])
        self.assertEqual(profile["scenarios"], {})

    def test_public_status_is_complete_at_the_cap_and_contains_no_numeric_score(self):
        profile = types.empty_profile()
        profile["questions_answered"] = 12
        status = pipeline.onboarding_status(profile)
        self.assertEqual(status, {
            "turn_limit": 12, "turns_used": 12, "turns_remaining": 0, "complete": True,
        })
        self.assertNotIn("score", repr(status).lower())
```

Also cover resume from legacy history without stage metadata, `questions_answered > 12` clamping, malformed profile containers, and post-completion refinement remaining possible without reopening intake.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
py -3 -m unittest discover -s backend/tests -p "test_surveyor_onboarding.py" -v
```

Expected: failures because the onboarding constants, attempted-stage bookkeeping, bounded signature, and status contract do not exist.

- [ ] **Step 3: Add the exact bounded completion constants and helper**

In `backend/surveyor/types.py` add:

```python
ONBOARDING_TURN_LIMIT = 12
ONBOARDING_PREFERENCE_LIMIT = 6
ONBOARDING_SCENARIO_LIMIT = 3
ONBOARDING_FREEFORM_LIMIT = 3


def onboarding_complete(profile: dict) -> bool:
    from . import freeform, scenarios

    profile = profile if isinstance(profile, dict) else {}
    try:
        answered = max(0, int(profile.get("questions_answered") or 0))
    except (TypeError, ValueError):
        answered = 0
    if answered >= ONBOARDING_TURN_LIMIT:
        return True
    signals = validate_signals(profile.get("signals"))
    scenario_answers = profile.get("scenarios") if isinstance(profile.get("scenarios"), dict) else {}
    freeform_answers = profile.get("freeform") if isinstance(profile.get("freeform"), dict) else {}
    return (
        len([key for key in SIGNAL_PRIORITY if signals.get(key)]) >= ONBOARDING_PREFERENCE_LIMIT
        and len([key for key in scenarios.IDS if scenario_answers.get(key)]) >= ONBOARDING_SCENARIO_LIMIT
        and len([key for key in freeform.KEYS if freeform.clean(freeform_answers.get(key))]) >= ONBOARDING_FREEFORM_LIMIT
    )
```

The local imports avoid circular module initialization. Change `operator_profile.is_complete()` to call `types.onboarding_complete()` after its existing container validation rather than requiring the exhaustive three-stage `profile_completeness()` value to equal `1.0`.

- [ ] **Step 4: Make question selection count attempted stage keys**

Add `attempted_keys()` that reads bounded known keys from assistant message metadata and falls back to existing preference text matching only for legacy preference rows. Change `next_step()` to accept history and select:

```python
def attempted_keys(history, stage):
    from . import freeform, scenarios
    known = {
        "preferences": set(QUESTIONS),
        "scenarios": set(scenarios.IDS),
        "freeform": set(freeform.KEYS),
    }.get(stage, set())
    output = []
    for message in history or []:
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        meta = message.get("meta") if isinstance(message.get("meta"), dict) else {}
        key = meta.get("key")
        if meta.get("stage") == stage and key in known and key not in output:
            output.append(key)
    if stage == "preferences":
        for key in asked_signals(history):
            if key in known and key not in output:
                output.append(key)
    return output


preference_attempts = attempted_keys(history, "preferences")
scenario_attempts = attempted_keys(history, "scenarios")
freeform_attempts = attempted_keys(history, "freeform")

if len(preference_attempts) < types.ONBOARDING_PREFERENCE_LIMIT:
    signal = next_signal(profile, preference_attempts)
    if signal:
        return {
            "stage": "preferences", "key": signal, "text": QUESTIONS[signal],
            "options": choices_for(signal), "intro": None,
        }

if len(scenario_attempts) < types.ONBOARDING_SCENARIO_LIMIT:
    scenario = scenarios.next_scenario_excluding(
        profile.get("scenarios") or {}, scenario_attempts,
    )
    if scenario:
        return {
            "stage": "scenarios", "key": scenario["id"], "text": scenario["text"],
            "options": scenarios.choices_for(scenario["id"]),
            "intro": STAGE_INTRO["scenarios"] if not scenario_attempts else None,
        }

if len(freeform_attempts) < types.ONBOARDING_FREEFORM_LIMIT:
    key, text = freeform.next_question_excluding(
        profile.get("freeform") or {}, freeform_attempts,
    )
    if key:
        return {
            "stage": "freeform", "key": key, "text": text, "options": [],
            "intro": STAGE_INTRO["freeform"] if not freeform_attempts else None,
        }

return {"stage": "done", "key": None, "text": CLOSING_FULL,
        "options": [], "intro": None}
```

Add the narrow helpers to their existing modules. They select only allow-listed IDs/keys and never write an inferred answer:

```python
# scenarios.py
def next_scenario_excluding(answers, attempted=()):
    answers = answers if isinstance(answers, dict) else {}
    blocked = {item for item in attempted or () if item in IDS}
    for scenario in SCENARIOS:
        if scenario["id"] not in blocked and not answers.get(scenario["id"]):
            return scenario
    return None


# freeform.py
def next_question_excluding(answers, attempted=()):
    answers = answers if isinstance(answers, dict) else {}
    blocked = {item for item in attempted or () if item in KEYS}
    for key in KEYS:
        if key not in blocked and not answers.get(key):
            return key, BY_KEY[key]
    return None, None
```

- [ ] **Step 5: Return safe progress from the pipeline**

Add:

```python
def onboarding_status(profile: dict) -> dict:
    try:
        used = max(0, int((profile or {}).get("questions_answered") or 0))
    except (TypeError, ValueError):
        used = 0
    used = min(types.ONBOARDING_TURN_LIMIT, used)
    return {
        "turn_limit": types.ONBOARDING_TURN_LIMIT,
        "turns_used": used,
        "turns_remaining": types.ONBOARDING_TURN_LIMIT - used,
        "complete": types.onboarding_complete(profile),
    }
```

Make `start()` and `turn()` call `qs.next_step(profile, history)` with the full stored history and include `onboarding_status(profile)` under `onboarding`. Retain `profile.complete` for compatibility, sourced from the same completion helper.

- [ ] **Step 6: Run focused and adjacent tests**

Run:

```powershell
py -3 -m unittest discover -s backend/tests -p "test_surveyor_onboarding.py" -v
py -3 -m unittest discover -s backend/tests -p "test_operator_profile.py" -v
py -3 -m unittest discover -s backend/tests -p "test_artifacts.py" -v
```

Expected: all pass; no score or CordiaAIE data appears in public Surveyor output.

- [ ] **Step 7: Commit Task 1**

```powershell
git add -- backend/surveyor/types.py backend/surveyor/question_strategy.py backend/surveyor/scenarios.py backend/surveyor/freeform.py backend/surveyor/operator_profile.py backend/surveyor/pipeline.py backend/tests/test_surveyor_onboarding.py backend/tests/test_operator_profile.py
git diff --cached --check
git commit -m "feat: bound Surveyor beta onboarding"
```

---

### Task 2: Make Surveyor's browser experience match the bounded FDE intake

**Files:**
- Create: `web/assets/cordia-surveyor-flow.js`
- Create: `web/test/surveyor_flow.test.js`
- Modify: `web/assets/cordia-surveyor.js`
- Modify: `web/surveyor.html`

**Interfaces:**
- Consumes the backend `onboarding` object from Task 1.
- Produces `CordiaSurveyorFlow.model(payload) -> {state, turnLimit, turnsUsed, turnsRemaining, complete}`.
- Produces only the fixed completion destination `profile.html#aiSection`.
- Does not produce a builder or certification destination.

- [ ] **Step 1: Write the failing browser-flow tests**

Create a UMD-compatible pure-model test:

```javascript
test('projects bounded progress and a fixed assessment completion action', () => {
  assert.deepEqual(flow.model({
    ok: true,
    onboarding: { turn_limit: 12, turns_used: 9, turns_remaining: 3, complete: false },
  }), {
    state: 'ready', turnLimit: 12, turnsUsed: 9, turnsRemaining: 3, complete: false,
  })
  assert.equal(flow.completionDestination(), 'profile.html#aiSection')
})

test('fails closed for inconsistent progress and never routes to builder or certification', () => {
  for (const payload of [
    null,
    { ok: true, onboarding: { turn_limit: 12, turns_used: 13, turns_remaining: -1, complete: true } },
    { ok: true, onboarding: { turn_limit: '12', turns_used: 0, turns_remaining: 12, complete: false } },
  ]) assert.deepEqual(flow.model(payload), { state: 'error' })
  assert.doesNotMatch(JSON.stringify(flow), /certification|builder\.html/i)
})
```

Add a VM page test that submits a draft, forces a rejected request containing a credential/path-shaped error, and asserts the textarea contains the original draft while the rendered error is fixed safe copy.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
node --test web/test/surveyor_flow.test.js
```

Expected: failure because `cordia-surveyor-flow.js` and the bounded DOM behavior do not exist.

- [ ] **Step 3: Implement the fail-closed progress model**

Expose only:

```javascript
function model(payload) {
  var item = payload && payload.onboarding
  if (!payload || payload.ok !== true || !item ||
      item.turn_limit !== 12 || !Number.isInteger(item.turns_used) ||
      !Number.isInteger(item.turns_remaining) ||
      item.turns_used < 0 || item.turns_used > 12 ||
      item.turns_remaining !== 12 - item.turns_used ||
      typeof item.complete !== 'boolean') return { state: 'error' }
  return {
    state: 'ready', turnLimit: 12, turnsUsed: item.turns_used,
    turnsRemaining: item.turns_remaining, complete: item.complete,
  }
}

function completionDestination() { return 'profile.html#aiSection' }
```

- [ ] **Step 4: Rewire the Surveyor modal without adding another state owner**

Load `cordia-surveyor-flow.js` before `cordia-surveyor.js`. Add a compact `aria-live="polite"` progress row that says `Question N of 12` during intake and `Intake complete` after completion.

Remove the pre-completion `Build my workspace` and `Show recommended certification` controls. Completion actions become:

```html
<button class="sv-act" data-act="assessment" type="button">
  Review what Cordia understands
</button>
<button class="sv-act" data-act="refine" type="button">Add more detail</button>
```

`assessment` navigates only to `CordiaSurveyorFlow.completionDestination()`. There must be no `certifications.html`, `assessment.html`, or `builder.html` string in `cordia-surveyor.js`.

Keep the submitted draft in a local variable until a valid success response. On transport, non-200, or malformed response, restore the draft if the user has not typed a replacement and show fixed bounded recovery copy. Never render `response.error` directly.

- [ ] **Step 5: Run focused and existing web tests**

Run:

```powershell
node --test web/test/surveyor_flow.test.js web/test/operator_profile.test.js
```

Expected: all pass, and the legacy `web/assessment.html` remains certification-specific but unreachable from Surveyor.

- [ ] **Step 6: Commit Task 2**

```powershell
git add -- web/assets/cordia-surveyor-flow.js web/assets/cordia-surveyor.js web/surveyor.html web/test/surveyor_flow.test.js web/test/operator_profile.test.js
git diff --cached --check
git commit -m "feat: align Surveyor UI with bounded intake"
```

---

### Task 3: Generate one canonical workspace atomically from Surveyor artifacts

**Files:**
- Create: `backend/surveyor/workspace_generation.py`
- Create: `backend/tests/test_workspace_generation.py`
- Modify: `backend/surveyor/store.py`
- Modify: `backend/surveyor/__init__.py`
- Modify: `backend/training_backend.py`

**Interfaces:**
- Consumes `pipeline.load_profile(email)`, `pipeline.compile_artifact_bundle(profile, connector_states)`, `adaptation.builder_defaults(profile)`, and `workspace_state.from_interface()`.
- Produces `workspace_generation.prepare(workspace_id, profile, connector_states) -> {name, description, definition, workspace, artifacts}`.
- Produces `store.ensure_initial_workspace(email, prepared) -> (workspace_id, created)`.
- Produces fixed authenticated `POST /surveyor/workspace/generate` with exact response `{ok, id, created}`.

- [ ] **Step 1: Write failing pure-generation and route tests**

The pure test must assert exact top-level fields and reuse of existing contracts:

```python
prepared = workspace_generation.prepare("workspace-1", completed_profile(), {"github": "confirmed"})
self.assertEqual(set(prepared), {
    "id", "name", "description", "definition", "workspace", "artifacts",
})
self.assertEqual(prepared["name"], "My Workspace")
self.assertEqual(prepared["workspace"]["id"], "workspace-1")
self.assertEqual(prepared["workspace"]["context_sources"], [
    {"kind": "artifact", "ref": "runtime/fde-tasks.md"},
])
self.assertIn("source/operator.md", prepared["artifacts"])
self.assertIn("runtime/fde-tasks.md", prepared["artifacts"])
self.assertNotIn("github_pat_PRIVATE", repr(prepared))
self.assertNotIn(r"C:\private\workspace", repr(prepared))
```

Route tests must prove:

- unauthenticated requests stop before profile/store reads;
- nonempty request bodies are rejected;
- incomplete onboarding returns 409 before workspace persistence;
- a completed owner receives only `{ok, id, created}`;
- repeated requests return the same ID with `created: false`;
- another account cannot receive or mutate that ID; and
- profile text, artifacts, definitions, paths, and secrets do not enter the response or audit payload.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
py -3 -m unittest discover -s backend/tests -p "test_workspace_generation.py" -v
```

Expected: failure because `workspace_generation`, the atomic store operation, and the route do not exist.

- [ ] **Step 3: Implement the pure preparation boundary**

Use fixed public naming and existing deterministic defaults:

```python
def prepare(workspace_id: str, profile: dict, connector_states: dict | None = None) -> dict:
    connector_states = artifacts.normalize_connector_states(connector_states or {})
    bundle = pipeline.compile_artifact_bundle(profile, connector_states)
    defaults = adaptation.builder_defaults(profile)
    definition = {
        "name": "My Workspace",
        "description": "A Cordia workspace shaped from your Surveyor profile.",
        "surface": deepcopy(defaults.get("surface") or {"type": "chat", "theme": "minimal"}),
        "agents": deepcopy(defaults.get("agents") or []),
        "tools": deepcopy(defaults.get("tools") or []),
        "workflow": deepcopy(defaults.get("workflow") or {"steps": []}),
    }
    state = workspace_state.from_interface(workspace_id, definition, connector_states)
    return {
        "id": workspace_id,
        "name": definition["name"],
        "description": definition["description"],
        "definition": definition,
        "workspace": state,
        "artifacts": bundle,
    }
```

Do not copy `defaults.reason`, profile free text, identifiers, evidence, raw artifacts, or connector credentials into the definition. The canonical workspace references the compiled mission by artifact ref.

- [ ] **Step 4: Implement one atomic initial-workspace store transaction**

`ensure_initial_workspace()` must use the existing `_lock` and one database transaction:

```python
def ensure_initial_workspace(email: str, prepared: dict) -> tuple[str, bool]:
    source = {
        key: value for key, value in prepared["artifacts"].items()
        if key.startswith("source/")
    }
    runtime = {
        key: value for key, value in prepared["artifacts"].items()
        if key.startswith("runtime/")
    }
    with _lock, _conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (email,))
        cursor.execute(
            "SELECT id FROM surveyor_interfaces WHERE email=%s AND archived=FALSE "
            "ORDER BY updated DESC LIMIT 1",
            (email,),
        )
        existing = cursor.fetchone()
        if existing:
            return existing[0], False
        cursor.execute(
            "INSERT INTO surveyor_interfaces"
            "(id,email,name,description,definition,theme) VALUES(%s,%s,%s,%s,%s,%s)",
            (prepared["id"], email, prepared["name"], prepared["description"],
             _J(prepared["definition"]), _J({})),
        )
        cursor.execute(
            "INSERT INTO surveyor_workspaces(id,email,state) VALUES(%s,%s,%s)",
            (prepared["id"], email, _J(prepared["workspace"])),
        )
        cursor.execute(
            "INSERT INTO surveyor_artifacts(email,source,runtime) VALUES(%s,%s,%s) "
            "ON CONFLICT(email) DO UPDATE SET source=EXCLUDED.source, "
            "runtime=EXCLUDED.runtime, updated=(now() AT TIME ZONE 'utc')",
            (email, _J(source), _J(runtime)),
        )
    return prepared["id"], True
```

The SQL uses parameter binding and the same JSON serialization helper as existing store writes. Split artifacts into `source/` and `runtime/` maps exactly as `save_artifacts()` does. Add fake-cursor tests that prove lock → existing check → inserts order, existing-account early return, rollback propagation, and no cross-owner query missing the email predicate.

- [ ] **Step 5: Add the fixed authenticated route**

Dispatch only exact path `/surveyor/workspace/generate`. The handler must:

```python
email, stop = self._surv_guard()
if stop:
    return
if not isinstance(body, dict) or body:
    self._json({"ok": False, "error": "workspace generation takes no fields"}, 400)
    return
profile = surveyor.pipeline.load_profile(email)
if not surveyor.types.onboarding_complete(profile):
    self._json({"ok": False, "error": "Complete Surveyor before building your workspace."}, 409)
    return
candidate = uuid.uuid4().hex
prepared = surveyor.workspace_generation.prepare(
    candidate, profile, surveyor.store.get_connector_states(email),
)
workspace_id, created = surveyor.store.ensure_initial_workspace(email, prepared)
if created:
    surveyor.store.log_event(email, "workspace_generated", {"id": workspace_id})
self._json({"ok": True, "id": workspace_id, "created": created})
```

The route does not accept a caller-selected ID, title, definition, artifacts, connector state, or destination URL.

- [ ] **Step 6: Run focused and canonical-state tests**

Run:

```powershell
py -3 -m unittest discover -s backend/tests -p "test_workspace_generation.py" -v
py -3 -m unittest discover -s backend/tests -p "test_workspace_state.py" -v
py -3 -m unittest discover -s backend/tests -p "test_artifacts.py" -v
```

Expected: all pass; legacy interface migration and canonical state behavior remain intact.

- [ ] **Step 7: Commit Task 3**

```powershell
git add -- backend/surveyor/workspace_generation.py backend/surveyor/store.py backend/surveyor/__init__.py backend/training_backend.py backend/tests/test_workspace_generation.py
git diff --cached --check
git commit -m "feat: generate canonical workspace from Surveyor"
```

---

### Task 4: Make the operator assessment launch Cordia-Agent workspace generation

**Files:**
- Create: `web/assets/cordia-workspace-generation.js`
- Create: `web/test/workspace_generation.test.js`
- Modify: `web/assets/operator-profile.js`
- Modify: `web/profile.html`
- Modify: `web/test/operator_profile.test.js`

**Interfaces:**
- Consumes `POST /surveyor/workspace/generate` from Task 3.
- Produces `CordiaWorkspaceGeneration.generate(options) -> Promise<{id, href, created}>`.
- Uses only `CordiaWorkspaceNavigation.buildWorkspaceNavigation(id)` for the destination.
- Changes the no-workspace operator-profile action to `{kind: "generate", label: "Build my workspace"}`.

- [ ] **Step 1: Write failing fixed-request and rendered-action tests**

Test exact transport and response validation:

```javascript
test('generation uses one fixed authenticated request and safe primary navigation', async () => {
  const calls = []
  const result = await generation.generate({
    fetch: async (...args) => {
      calls.push(args)
      return { ok: true, json: async () => ({ ok: true, id: 'workspace-1', created: true }) }
    },
    navigation,
  })
  assert.deepEqual(calls, [[
    '/surveyor/workspace/generate',
    { method: 'POST', headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin', body: '{}' },
  ]])
  assert.deepEqual(result, {
    id: 'workspace-1', href: '/dashboard/?workspace=workspace-1', created: true,
  })
})
```

Test malformed IDs, credential/path-shaped IDs, unknown fields, non-OK status, invalid JSON, rejection, and duplicate click suppression. Public errors must be the fixed sentence `Cordia could not build your workspace. Try again.` and must not include the server error.

Update the operator-profile model expectation:

```javascript
assert.deepEqual(model.primaryAction, {
  kind: 'generate', label: 'Build my workspace',
})
```

and assert the model contains no `builder.html` or server-provided URL.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
node --test web/test/workspace_generation.test.js web/test/operator_profile.test.js
```

Expected: failures because the coordinator and `generate` action do not exist.

- [ ] **Step 3: Implement the fixed generation coordinator**

The UMD module validates the exact safe response shape:

```javascript
async function generate(options) {
  var response = await options.fetch('/surveyor/workspace/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: '{}',
  })
  var payload = await response.json().catch(function () { return null })
  if (!response.ok || !payload || payload.ok !== true ||
      typeof payload.created !== 'boolean' ||
      Object.keys(payload).sort().join('|') !== 'created|id|ok') throw new Error('generation failed')
  var target = options.navigation.buildWorkspaceNavigation(payload.id)
  if (!target) throw new Error('generation failed')
  return { id: payload.id, href: target.href, created: payload.created }
}
```

No caller-selected path, payload, name, workspace ID, or URL is accepted.

- [ ] **Step 4: Render and execute the Cordia-Agent generation action**

In `operator-profile.js`, return `kind: 'generate'` when the safe next action is `create_interface` and no safe latest workspace exists.

In `profile.html`, load the new module after `workspace-navigation.js`. `actionMarkup()` renders:

```html
<button class="btn" type="button" data-generate-workspace>Build my workspace</button>
```

Use one in-flight flag. Disable the button and show `Cordia is building your workspace…`; call the fixed coordinator; then `location.replace(result.href)`. On any failure, re-enable the control and show only the fixed bounded message. Existing workspace links and Surveyor refinement controls retain their behavior.

- [ ] **Step 5: Run focused web tests**

Run:

```powershell
node --test web/test/workspace_generation.test.js web/test/operator_profile.test.js
```

Expected: all pass; primary new-user flow contains no legacy builder or certification route.

- [ ] **Step 6: Commit Task 4**

```powershell
git add -- web/assets/cordia-workspace-generation.js web/assets/operator-profile.js web/profile.html web/test/workspace_generation.test.js web/test/operator_profile.test.js
git diff --cached --check
git commit -m "feat: build workspace from operator assessment"
```

---

### Task 5: Prove the complete Release 1 journey across backend and browser boundaries

**Files:**
- Create: `backend/tests/test_beta_intake_journey.py`
- Create: `web/test/beta_intake_journey.test.js`
- Modify only if the integration tests expose a real contract gap: files already owned by Tasks 1–4.

**Interfaces:**
- Consumes all Release 1 contracts.
- Produces no new production API.
- Proves one account's profile, artifacts, interface compatibility row, canonical workspace, navigation, and recovery remain bound to the same identity and workspace ID.

- [ ] **Step 1: Write the backend journey test**

Use an in-memory store double but call the real `pipeline.start()`, `pipeline.turn()`, `workspace_generation.prepare()`, route dispatch, and `workspace_state` logic. Drive the exact twelve stages. For preference prompts, use an offered choice when present and a safe sentence for free text. For scenario prompts, use the first exact offered choice. For freeform prompts, use safe user text.

The final assertions are:

```python
self.assertTrue(last_turn["onboarding"]["complete"])
self.assertEqual(last_turn["onboarding"]["turns_used"], 12)
self.assertEqual(len([m for m in memory.messages if m["role"] == "user"]), 12)
self.assertIn("source/operator.md", memory.artifacts)
self.assertIn("runtime/fde-tasks.md", memory.artifacts)
self.assertEqual(generated_response, {
    "ok": True, "id": memory.workspace_id, "created": True,
})
self.assertEqual(repeated_response, {
    "ok": True, "id": memory.workspace_id, "created": False,
})
self.assertEqual(workspace_response["workspace"]["id"], memory.workspace_id)
self.assertEqual(memory.interface_id, memory.workspace_id)
self.assertNotIn("score", repr(public_trace).lower())
self.assertNotIn("certification", repr(public_trace).lower())
```

Add a second account and prove the first account's workspace returns 404 and is absent from its interface list.

- [ ] **Step 2: Write the browser continuity test**

Execute the real browser-shared modules in a VM:

1. operator assessment returns `kind: generate`;
2. fixed generation returns `workspace-1`;
3. safe navigation opens `/dashboard/?workspace=workspace-1`;
4. subsequent authentication resume reads `/surveyor/interfaces` and opens that same URL; and
5. a failed/malformed first interface never scans to another record or constructs a URL.

Assert the source files used by this path contain no Surveyor link to `assessment.html`, `certifications.html`, or `builder.html`.

- [ ] **Step 3: Run both journey tests and verify RED if any seam remains**

Run:

```powershell
py -3 -m unittest discover -s backend/tests -p "test_beta_intake_journey.py" -v
node --test web/test/beta_intake_journey.test.js
```

Expected before any required seam fix: a precise contract failure, not an import or harness failure. If both are already green, do not change production code.

- [ ] **Step 4: Make only integration-discovered fixes**

Any production fix must stay within the existing Release 1 interfaces. Do not add another endpoint, workspace store, profile schema, browser destination, connector behavior, or CordiaAIE dependency. Add a focused regression for every changed branch.

- [ ] **Step 5: Run all Release 1 focused suites**

Run:

```powershell
py -3 -m unittest discover -s backend/tests -p "test_surveyor_onboarding.py" -v
py -3 -m unittest discover -s backend/tests -p "test_workspace_generation.py" -v
py -3 -m unittest discover -s backend/tests -p "test_beta_intake_journey.py" -v
node --test web/test/auth_flow.test.js web/test/auth_workspace_resume.test.js web/test/auth_page_resume.integration.test.js web/test/operator_profile.test.js web/test/surveyor_flow.test.js web/test/workspace_generation.test.js web/test/beta_intake_journey.test.js
```

Expected: all pass.

- [ ] **Step 6: Commit Task 5**

```powershell
git add -- backend/tests/test_beta_intake_journey.py web/test/beta_intake_journey.test.js
git add -- backend/surveyor/types.py backend/surveyor/question_strategy.py backend/surveyor/scenarios.py backend/surveyor/freeform.py backend/surveyor/operator_profile.py backend/surveyor/pipeline.py backend/surveyor/workspace_generation.py backend/surveyor/store.py backend/training_backend.py web/assets/cordia-surveyor-flow.js web/assets/cordia-surveyor.js web/assets/operator-profile.js web/assets/cordia-workspace-generation.js web/profile.html
git diff --cached --check
git commit -m "test: prove beta intake continuity"
```

Before committing, inspect the staged file list and unstage any production file that did not require an integration fix.

---

### Task 6: Reconcile evidence, run full verification, and prepare Release 1 for review

**Files:**
- Modify: `backend/surveyor/README.md`
- Modify: `docs/TODO_CORDIA_VERTICAL_SLICE.md`

**Interfaces:**
- Documents only directly demonstrated Release 1 behavior.
- Leaves connector gateway, ASK continuation, custom connectors, billing, Desktop packaging/sync, Alidora actions, and public deployment acceptance open.

- [ ] **Step 1: Update documentation conservatively**

Document:

- Surveyor's 12-turn beta intake allocation;
- the operator profile as the non-scored Surveyor assessment;
- `POST /surveyor/workspace/generate` as an authenticated no-field idempotent operation;
- the compatibility-interface plus canonical-workspace ownership model;
- Cordia Agent/FDE ownership of workspace generation;
- the legacy manual builder remaining non-primary; and
- CordiaAIE assessment remaining separate.

In the vertical-slice checklist, check only items directly supported by the new route and journey tests. Keep public deployment, connector breadth, billing, Desktop, ASK resume, and complete beta acceptance unchecked.

- [ ] **Step 2: Run the complete backend suite**

Run:

```powershell
py -3 -m unittest discover -s backend/tests -v
```

Expected: zero failures and zero errors. If the selected interpreter lacks a locked dependency, use the project's configured Python 3.12 runtime and record the exact path in the task report rather than skipping the test.

- [ ] **Step 3: Run the complete web suite**

Run every file explicitly for Windows reliability:

```powershell
node --test web/test/auth_flow.test.js web/test/auth_page_resume.integration.test.js web/test/auth_workspace_resume.test.js web/test/operator_profile.test.js web/test/surveyor_flow.test.js web/test/workspace_generation.test.js web/test/beta_intake_journey.test.js
```

Expected: zero failures.

- [ ] **Step 4: Verify the unchanged production workspace and Desktop entry contracts**

Run:

```powershell
Set-Location dashboard-app
npm.cmd ci
npm.cmd test
npm.cmd run build
Set-Location ..\desktop
npm.cmd ci
npm.cmd test
npm.cmd run verify:dashboard-release
Set-Location ..
```

Expected: dashboard tests/build and Desktop tests/release-provenance verification pass. If the dashboard build rewrites tracked release assets without a source change, restore only those generated bytes from `HEAD` after verifying provenance; do not commit unrelated release drift.

- [ ] **Step 5: Run syntax, privacy, and diff checks**

Run:

```powershell
py -3 -m py_compile backend/surveyor/types.py backend/surveyor/question_strategy.py backend/surveyor/scenarios.py backend/surveyor/freeform.py backend/surveyor/operator_profile.py backend/surveyor/pipeline.py backend/surveyor/workspace_generation.py backend/surveyor/store.py backend/training_backend.py
node --check web/assets/cordia-surveyor-flow.js
node --check web/assets/cordia-surveyor.js
node --check web/assets/cordia-workspace-generation.js
node --check web/assets/operator-profile.js
git diff --check
git status --short
```

Search the Release 1 public response and browser models for forbidden fields:

```powershell
rg -n "raw_artifacts|ciphertext|authorization|password|api_key|local_path|percent_complete|certification" backend/tests/test_beta_intake_journey.py web/test/beta_intake_journey.test.js
```

Any match must be an explicit negative assertion or test sentinel, never a public expected value.

- [ ] **Step 6: Commit documentation and evidence**

```powershell
git add -- backend/surveyor/README.md docs/TODO_CORDIA_VERTICAL_SLICE.md
git diff --cached --check
git commit -m "docs: record beta intake continuity evidence"
```

- [ ] **Step 7: Request independent code review**

Review the complete branch against the approved spec, with special attention to:

- Cordia Agent/FDE ownership;
- 12-turn semantics and resume behavior;
- CordiaAIE separation;
- atomic and owner-scoped generation;
- duplicate-click/server idempotency;
- compatibility interface vs canonical workspace ownership;
- public response privacy; and
- truthful checklist claims.

Resolve every Critical or Important finding with a separate RED → GREEN fix commit, then rerun the full verification matrix.

---

## Release 1 Completion Gate

Release 1 is complete only when:

- a verified account reaches Surveyor;
- Surveyor completes or safely caps at twelve user turns;
- the non-scored operator assessment is inspectable;
- the Cordia Agent generates one canonical workspace without the user manually building agent/tool forms;
- duplicate generation returns the same workspace;
- Dashboard renders that workspace;
- logout/login resumes that exact workspace;
- another account cannot read it;
- the legacy CordiaAIE assessment is not in the path;
- all focused and full tests pass;
- an independent review reports no Critical or Important findings; and
- documentation does not claim the release is publicly live until Hostinger deployment verification occurs.
