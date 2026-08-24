# Cordia Thin-Spine MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one honest Cordia journey from authenticated profile calibration through a real Cordia Agent turn, connector setup, bounded skill execution, and a visibly updated saved workspace.

**Architecture:** Adapt the existing authentication, PostgreSQL persistence, vault, capability gateway, canonical workspace state, and React workspace in place. Add four focused backend modules—profile calibration, model provider, action validation, and connector runtime—while keeping the existing `training_backend.py` routes as the HTTP composition root and preserving legacy interface rows only as an internal compatibility dependency.

**Tech Stack:** Python 3.12 standard library HTTP server, PostgreSQL/psycopg2, cryptography/Fernet, React 19, Vite 7, Node 20.19+ test runner, Electron compatibility shell.

**Spec:** `docs/superpowers/specs/2026-08-20-cordia-thin-spine-design.md`

## Global Constraints

- The user experiences one product: sign in, profile calibration, and the primary Cordia workspace. Existing Surveyor, builder, interface, and dashboard routes may remain only as compatibility layers.
- Owner-scoped PostgreSQL structured data is authoritative. `source/memory.md` is a compiled artifact, never a filesystem file or a second state owner.
- The Cordia Agent uses one configured real provider. Missing configuration and provider failure return an honest unavailable state; deterministic code may not fabricate speech, proposals, actions, or artifact changes.
- Every model response is untrusted and must validate as exactly one of `speak`, `propose_connector`, `create_artifact`, `propose_skill`, or `run_approved_skill` before use.
- Generic connector setup supports only `api_key`, `openapi`, and `remote_mcp`; GitHub remains the built-in example. OAuth-only services remain explicitly unavailable.
- Credentials travel directly to the encrypted vault and become opaque secret references before any agent continuation. They never enter prompts, transcripts, workspace state, artifacts, responses, or audit payloads.
- Connector availability changes only after a real bounded connection test succeeds.
- A skill is declarative data. No generated executable code, arbitrary shell, arbitrary request URL, hidden prompt, raw secret, or unbounded provider payload is accepted.
- DashView is the default. DerivedView uses bounded stored results. LiveView is absent unless the connector declares support and the user explicitly enables it.
- No task may claim `Verified with real provider` from a fake adapter, deterministic double, schema test, or mocked route. Real-provider evidence must record the exact production route and a safe observable result.
- No task may claim `Verified live` until the separately authorized public deployment is directly exercised.
- At this plan's `origin/main` base, `backend/surveyor/model_provider.py` does not exist; only the inline provider call in `training_backend.py` and the `llm.py` selection seam exist. Task 3 creates and verifies the focused module on this branch; uncommitted files in another worktree are reference material, not built product evidence.
- CordiaAIE, Alidora authoring/execution, billing enforcement, broad Desktop packaging, enterprise controls, background automations, and provider-specific OAuth are outside this plan.

## File Responsibility Map

- `backend/surveyor/profile_calibration.py`: strict `cordia-profile-v1` validation, signed survey-state tokens, and deterministic `source/memory.md` compilation.
- `backend/surveyor/model_provider.py`: the single OpenAI-compatible provider configuration/call boundary with explicit unavailable/failure errors.
- `backend/surveyor/cordia_agent.py`: prompt construction, exact five-envelope validation, and safe public action projection.
- `backend/surveyor/connector_runtime.py`: strict connector manifests, setup validation, bounded API-key/OpenAPI/MCP probes, and safe connector records.
- `backend/surveyor/store.py`: existing owner-scoped persistence extended with profile calibration and connector records; no new state owner.
- `backend/surveyor/workspace_generation.py`: composes profile memory into the initial canonical workspace and artifacts.
- `backend/surveyor/workspace_state.py`: applies validated artifact/connector/skill projections and increments workspace revision.
- `backend/surveyor/capability_gateway.py` and `backend/surveyor/skills.py`: validate and run generated declarative skills through the existing permission gate.
- `backend/training_backend.py`: fixed authenticated HTTP routes and orchestration only; no provider, connector, or action schema logic remains inline.
- `dashboard-app/src/api.js`: fixed browser request contracts for profile completion, turns, connector setup, and skill execution.
- `dashboard-app/src/workspace-view.js`: renderer-safe response models and interaction controllers.
- `dashboard-app/src/WorkspaceView.jsx`: one continuous left-agent/right-artifact experience.

---

## Sprint 1 — Profile Memory and Continuity

### Task 1: Strict Profile Calibration and Compiled Workspace Memory

**Files:**
- Create: `backend/surveyor/profile_calibration.py`
- Modify: `backend/surveyor/__init__.py`
- Modify: `backend/surveyor/store.py`
- Modify: `backend/surveyor/workspace_generation.py`
- Test: `backend/tests/test_profile_calibration.py`
- Test: `backend/tests/test_profile_memory.py`

**Interfaces:**
- Consumes: the exact `cordia-profile-v1` shape in the approved spec and existing `store.save_artifacts(email, bundle)` behavior.
- Produces: `validate_result(value: object) -> dict`, `compile_memory(profile: dict) -> str`, `is_calibrated(profile: object) -> bool`, `store.save_profile_calibration(email: str, calibration: dict) -> None`, and `store.get_profile_calibration(email: str) -> dict | None`.

- [ ] **Step 1: Write strict contract tests before production code**

```python
VALID = {
    "schema_version": "cordia-profile-v1",
    "survey_version": "research-2026-08",
    "profile_id": "profile_018f0f4d",
    "communication": {
        "explicit_implicit": 7.3,
        "detail_big_picture": 2.0,
        "indirect_direct": 3.5,
        "reasoning_before_conclusion": True,
        "infer_unstated_context": True,
    },
    "domains": [{"id": "technology_software", "self_rating": 5,
                 "calibration": "consistent"}],
    "personality": {},
    "natural_requests": ["Show me how the dependencies fit together."],
    "completed_at": "2026-08-20T12:00:00Z",
}

def test_validate_result_returns_a_copy_of_the_exact_v1_contract(self):
    result = profile_calibration.validate_result(VALID)
    self.assertEqual(result, VALID)
    self.assertIsNot(result, VALID)

def test_validate_result_rejects_unknown_fields_and_out_of_range_scores(self):
    for bad in (
        {**VALID, "unexpected": "model prompt injection"},
        {**VALID, "communication": {**VALID["communication"],
                                     "explicit_implicit": 10.1}},
    ):
        with self.assertRaises(ValueError):
            profile_calibration.validate_result(bad)
```

- [ ] **Step 2: Run the profile contract tests and confirm RED**

Run: `Set-Location backend; py -3 -m unittest tests.test_profile_calibration -v`

Expected: import failure for `surveyor.profile_calibration`.

- [ ] **Step 3: Implement the exact validator and memory compiler**

```python
SCHEMA_VERSION = "cordia-profile-v1"
_TOP_KEYS = {"schema_version", "survey_version", "profile_id", "communication",
             "domains", "personality", "natural_requests", "completed_at"}
_COMMUNICATION_KEYS = {"explicit_implicit", "detail_big_picture",
                       "indirect_direct", "reasoning_before_conclusion",
                       "infer_unstated_context"}

def validate_result(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != _TOP_KEYS:
        raise ValueError("profile result does not match cordia-profile-v1")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported profile schema")
    communication = value.get("communication")
    if not isinstance(communication, dict) or set(communication) != _COMMUNICATION_KEYS:
        raise ValueError("profile communication result is invalid")
    for key in ("explicit_implicit", "detail_big_picture", "indirect_direct"):
        score = communication.get(key)
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 10:
            raise ValueError("profile communication score is invalid")
    if not all(isinstance(communication[key], bool) for key in
               ("reasoning_before_conclusion", "infer_unstated_context")):
        raise ValueError("profile communication choices are invalid")
    for key, limit in (("survey_version", 80), ("profile_id", 120)):
        field = value.get(key)
        if not isinstance(field, str) or not re.fullmatch(r"[A-Za-z0-9._:-]+", field) or len(field) > limit:
            raise ValueError(f"profile {key} is invalid")
    domains = value.get("domains")
    if not isinstance(domains, list) or len(domains) > 20:
        raise ValueError("profile domains are invalid")
    for row in domains:
        if (not isinstance(row, dict)
                or set(row) != {"id", "self_rating", "calibration"}
                or not isinstance(row["id"], str)
                or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", row["id"])
                or isinstance(row["self_rating"], bool)
                or not isinstance(row["self_rating"], int)
                or not 1 <= row["self_rating"] <= 5
                or row["calibration"] not in {"underestimated", "consistent", "overestimated", "unknown"}):
            raise ValueError("profile domain row is invalid")
    personality = value.get("personality")
    if personality != {}:
        raise ValueError("profile personality result is invalid")
    requests = value.get("natural_requests")
    if (not isinstance(requests, list) or len(requests) > 20
            or any(not isinstance(item, str) or not item.strip() or len(item) > 600
                   for item in requests)):
        raise ValueError("profile natural requests are invalid")
    completed = value.get("completed_at")
    if not isinstance(completed, str) or not completed.endswith("Z"):
        raise ValueError("profile completion time is invalid")
    datetime.fromisoformat(completed[:-1] + "+00:00")
    return deepcopy(value)

def compile_memory(profile: dict) -> str:
    validated = validate_result(profile)
    lines = ["# Workspace Memory", "", "## Communication policy"]
    communication = validated["communication"]
    if communication["reasoning_before_conclusion"]:
        lines.append("- Explain reasoning before conclusions.")
    lines.append("- Label assumptions when inferring unstated context."
                 if communication["infer_unstated_context"]
                 else "- Ask before relying on unstated context.")
    lines.extend(["", "## Domain context"])
    for domain in validated["domains"]:
        label = {"technology_software": "Technology and software"}.get(
            domain["id"], domain["id"].replace("_", " ").capitalize())
        familiarity = {1: "new", 2: "basic", 3: "working", 4: "strong", 5: "advanced"}[
            domain["self_rating"]]
        lines.append(f"- {label}: {familiarity} familiarity.")
    lines.extend(["", "## Observed workspace intent"])
    intent_rules = {
        "dependency": "Understand system dependencies.",
        "risk": "Identify operational risks.",
        "evidence": "Analyze evidence before recommending changes.",
        "connect": "Connect work systems into one visible workspace.",
    }
    request_text = " ".join(validated["natural_requests"]).lower()
    for marker, sentence in intent_rules.items():
        if marker in request_text:
            lines.append("- " + sentence)
    lines.extend(["", "## Evidence", "- Source: Cordia Profile Calibration",
                  f"- Survey version: {validated['survey_version']}",
                  f"- Profile schema: {SCHEMA_VERSION}"])
    return "\n".join(lines) + "\n"
```

The initial v1 implementation accepts `personality` only as the exact empty object shown in the approved contract. The survey engineer's canonical payload must define any personality fields before Cordia adds them through a schema-version change. The implementation must bound: `survey_version` to 80 safe identifier characters, `profile_id` to 120 safe identifier characters, domain count to 20, natural request count to 20, and every natural request to 600 characters. `compile_memory` may use fixed sentence templates and allow-listed intent markers only; it must exclude `profile_id`, natural-request verbatim text, local-path-shaped strings, credential-shaped strings, and unknown fields.

- [ ] **Step 4: Add memory snapshot and privacy tests**

```python
def test_compile_memory_is_bounded_inspectable_and_behavioral(self):
    memory = profile_calibration.compile_memory(VALID)
    self.assertIn("# Workspace Memory", memory)
    self.assertIn("Explain reasoning before conclusions.", memory)
    self.assertIn("Technology and software: advanced familiarity.", memory)
    self.assertIn("Survey version: research-2026-08", memory)
    self.assertNotIn("profile_018f0f4d", memory)
    self.assertNotIn("Show me how the dependencies fit together.", memory)
    self.assertLessEqual(len(memory), 5000)

def test_compile_memory_never_changes_permission_or_fact_truth(self):
    memory = profile_calibration.compile_memory(VALID)
    for forbidden in ("ALLOW", "connected", "approved", "live connector"):
        self.assertNotIn(forbidden, memory)
```

- [ ] **Step 5: Extend the existing profile table instead of creating another owner**

Add `ALTER TABLE surveyor_profiles ADD COLUMN IF NOT EXISTS profile_calibration JSONB;` to the existing idempotent schema bootstrap and implement owner-keyed read/write functions:

```python
def save_profile_calibration(email: str, calibration: dict) -> None:
    with _conn() as connection, connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO surveyor_profiles(email, profile_calibration)
            VALUES (%s,%s)
            ON CONFLICT (email) DO UPDATE SET
                profile_calibration=EXCLUDED.profile_calibration,
                updated=(now() AT TIME ZONE 'utc')
        """, (email, _J(calibration)))

def get_profile_calibration(email: str) -> dict | None:
    with _conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT profile_calibration FROM surveyor_profiles WHERE email=%s",
                       (email,))
        row = cursor.fetchone()
    return deepcopy(row[0]) if row and isinstance(row[0], dict) else None
```

- [ ] **Step 6: Make workspace preparation accept the compiled memory without replacing legacy compatibility state**

Change the signature to:

```python
def prepare(workspace_id: str, profile: dict, connector_states: dict | None = None,
            calibration: dict | None = None) -> dict:
```

When `calibration` is present, validate it, add `source/memory.md` to the existing bundle, set the initial description to `A Cordia workspace shaped from your profile calibration.`, and preserve the existing legacy interface definition because `surveyor_runs.interface_id` still depends on it.

- [ ] **Step 7: Run focused and adjacent backend tests**

Run: `Set-Location backend; py -3 -m unittest tests.test_profile_calibration tests.test_profile_memory tests.test_workspace_generation -v`

Expected: all tests pass and the existing workspace-generation tests remain green.

- [ ] **Step 8: Commit the independently reviewable memory slice**

```powershell
git add backend/surveyor/profile_calibration.py backend/surveyor/__init__.py backend/surveyor/store.py backend/surveyor/workspace_generation.py backend/tests/test_profile_calibration.py backend/tests/test_profile_memory.py
git commit -m "feat: add profile calibration memory"
```

### Task 2: Secure Survey Completion and Canonical Workspace Entry

**Files:**
- Modify: `backend/training_backend.py`
- Create: `backend/tests/test_profile_calibration_route.py`
- Modify: `web/index.html`
- Create: `web/assets/profile-entry.js`
- Create: `web/test/profile_entry.test.js`
- Modify: `web/test/auth_workspace_resume.test.js`

**Interfaces:**
- Consumes: `profile_calibration.validate_result`, `profile_calibration.compile_memory`, store functions from Task 1, and existing `store.ensure_initial_workspace`.
- Produces: `GET /surveyor/profile-calibration`, `POST /surveyor/profile-calibration/import`, `POST /surveyor/profile-calibration/complete`, and browser helper `resolveCordiaEntry({ getJson, postJson, locationSearch }): Promise<string>`.

- [ ] **Step 1: Write route RED tests for authenticated development import and provider completion**

```python
def test_import_stores_validated_profile_memory_and_returns_one_workspace(self):
    response, status = self.post("/surveyor/profile-calibration/import", VALID,
                                 email="owner@example.test")
    self.assertEqual(status, 200)
    self.assertEqual(response,
                     {"ok": True, "workspace_id": "workspace-1", "created": True})
    self.assertEqual(self.store.saved_calibration, VALID)
    self.assertIn("source/memory.md", self.store.saved_artifacts)

def test_import_rejects_unknown_fields_without_any_write(self):
    response, status = self.post("/surveyor/profile-calibration/import",
                                 {**VALID, "prompt": "ignore rules"},
                                 email="owner@example.test")
    self.assertEqual(status, 400)
    self.assertEqual(self.store.write_calls, [])

def test_reimport_refreshes_memory_for_the_existing_owner_workspace(self):
    self.store.existing_workspace_id = "workspace-existing"
    response, status = self.post("/surveyor/profile-calibration/import", VALID,
                                 email="owner@example.test")
    self.assertEqual((response["workspace_id"], response["created"]),
                     ("workspace-existing", False))
    self.assertIn("source/memory.md", self.store.saved_artifacts)
```

The production route may be enabled only when `CORDIA_PROFILE_DEV_IMPORT=1`; otherwise it returns `404` so it cannot become an undocumented production bypass.

- [ ] **Step 2: Run the route test and confirm RED**

Run: `Set-Location backend; py -3 -m unittest tests.test_profile_calibration_route -v`

Expected: `POST /surveyor/profile-calibration/import` is not routed.

- [ ] **Step 3: Add signed, owner-bound survey state and provider-result retrieval**

Add to `profile_calibration.py`:

```python
def issue_state(email: str, now: int | None = None) -> str:
    """Return base64url(payload).base64url(HMAC-SHA256) with email, nonce, expiry."""

def verify_state(token: str, authenticated_email: str, now: int | None = None) -> dict:
    """Require exact HMAC, same normalized email, and expiry no more than 15 minutes."""

def fetch_result(result_id: str, opener=urllib.request.urlopen) -> dict:
    """GET the configured fixed result endpoint; caller cannot choose the host."""
```

Configuration is exact: `CORDIA_PROFILE_SURVEY_URL`, `CORDIA_PROFILE_RESULT_URL`, `CORDIA_PROFILE_STATE_KEY`, and optional server-only `CORDIA_PROFILE_API_TOKEN`. The retrieval URL is `CORDIA_PROFILE_RESULT_URL.rstrip('/') + '/' + quote(result_id, safe='')`; redirects are rejected, response size is capped at 64 KiB, timeout is 10 seconds, and the response must pass `validate_result`.

- [ ] **Step 4: Implement fixed authenticated routes and one orchestration helper**

```python
def _complete_profile_calibration(email, result):
    calibration = surveyor.profile_calibration.validate_result(result)
    surveyor.store.save_profile_calibration(email, calibration)
    candidate = uuid.uuid4().hex
    prepared = surveyor.workspace_generation.prepare(
        candidate, surveyor.pipeline.load_profile(email),
        surveyor.store.get_connector_states(email), calibration)
    workspace_id, created = surveyor.store.ensure_initial_workspace(email, prepared)
    current = surveyor.store.get_artifacts(email) or {}
    current["source/memory.md"] = surveyor.profile_calibration.compile_memory(calibration)
    surveyor.store.save_artifacts(email, current)
    return {"ok": True, "workspace_id": workspace_id, "created": created}
```

`/import` passes the request body to this helper only in controlled development mode. `/complete` accepts exactly `{state, result_id}`, verifies the authenticated owner, fetches the provider result server-to-server, and calls the same helper. `GET /surveyor/profile-calibration` returns exactly `{ok, calibrated, workspace_id}` for calibrated owners or `{ok, calibrated: false, survey_url}` where `survey_url` is the fixed configured survey URL with a fresh signed state. It never creates a workspace on GET and never accepts a return URL from the browser. If the provider endpoint does not exist yet, completion is Built but remains Not yet verified with the external survey.

- [ ] **Step 5: Write browser entry tests before changing navigation**

```javascript
test('a calibrated owner resumes one canonical workspace', async () => {
  const destination = await resolveCordiaEntry({
    getJson: async (path) => path === '/surveyor/profile-calibration'
      ? { ok: true, calibrated: true, workspace_id: 'workspace-1' }
      : null,
    postJson: async () => { throw new Error('must not post') },
    locationSearch: '',
  })
  assert.equal(destination, '/dashboard/?workspace=workspace-1')
})

test('an uncalibrated owner receives only the configured survey start URL', async () => {
  const destination = await resolveCordiaEntry({
    getJson: async () => ({ ok: true, calibrated: false,
                            survey_url: 'https://cordia-survey1.vercel.app/survey?state=opaque' }),
    postJson: async () => { throw new Error('must not post') },
    locationSearch: '',
  })
  assert.equal(destination,
               'https://cordia-survey1.vercel.app/survey?state=opaque')
})
```

- [ ] **Step 6: Implement one entry resolver and use it after cookie restore and login**

`web/assets/profile-entry.js` must accept only:

```javascript
export async function resolveCordiaEntry({ getJson, postJson, locationSearch }) {
  const query = new URLSearchParams(locationSearch)
  if (query.has('state') || query.has('result_id')) {
    if (!query.get('state') || !query.get('result_id')) return '/'
    const completed = await postJson('/surveyor/profile-calibration/complete', {
      state: query.get('state'), result_id: query.get('result_id'),
    })
    return safeWorkspaceHref(completed.workspace_id) || '/'
  }
  const entry = await getJson('/surveyor/profile-calibration')
  if (entry.calibrated) return safeWorkspaceHref(entry.workspace_id) || '/'
  return safeSurveyHref(entry.survey_url) || '/'
}
```

Do not accept caller-supplied `next` URLs, localStorage workspace IDs, raw result JSON in the query string, or cross-owner result bindings.

- [ ] **Step 7: Run Sprint 1 tests**

Run: `Set-Location backend; py -3 -m unittest tests.test_profile_calibration tests.test_profile_memory tests.test_profile_calibration_route tests.test_workspace_generation -v`

Run: `Set-Location web; node --test test/profile_entry.test.js test/auth_workspace_resume.test.js`

Expected: all listed tests pass. The route test must exercise `H.do_POST`, not call only the helper.

- [ ] **Step 8: Commit the continuous-entry slice**

```powershell
git add backend/training_backend.py backend/tests/test_profile_calibration_route.py web/index.html web/assets/profile-entry.js web/test/profile_entry.test.js web/test/auth_workspace_resume.test.js
git commit -m "feat: enter Cordia through profile calibration"
```

## Sprint 2 — Real Agent and Five Actions

### Task 3: Honest Model Provider Boundary

**Files:**
- Create: `backend/surveyor/model_provider.py`
- Modify: `backend/surveyor/llm.py`
- Modify: `backend/surveyor/__init__.py`
- Modify: `backend/training_backend.py`
- Create: `backend/tests/test_model_provider.py`
- Create: `backend/tests/test_agent_model_status.py`

**Interfaces:**
- Consumes: existing `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_KEY` environment variables and the existing OpenAI-compatible response shape.
- Produces: `ModelUnavailable`, `ModelFailure`, `configuration() -> dict`, `call(system: str, user: str, max_tokens: int = 900, opener=urllib.request.urlopen) -> str`, and `status() -> dict`.

- [ ] **Step 1: Write provider RED tests against production-shaped HTTP responses**

```python
def test_missing_key_is_unavailable_and_never_calls_network(self):
    with patch.dict(os.environ, {"LLM_KEY": ""}, clear=True):
        with self.assertRaises(model_provider.ModelUnavailable):
            model_provider.call("system", "user", opener=self.fail_opener)

def test_valid_response_returns_only_assistant_content(self):
    opener = FakeOpener({"choices": [{"message": {"content": "Hello"}}]})
    with configured_provider():
        self.assertEqual(model_provider.call("system", "user", opener=opener), "Hello")
    self.assertEqual(opener.timeout, 30)
    self.assertNotIn("test-secret", repr(opener.public_trace))

def test_malformed_or_failed_provider_never_falls_back_to_fake_speech(self):
    for response in ({}, {"choices": []}, {"choices": [{"message": {"content": ""}}]}):
        with self.assertRaises(model_provider.ModelFailure):
            model_provider.call("system", "user", opener=FakeOpener(response))
```

- [ ] **Step 2: Run the provider suite and confirm RED**

Run: `Set-Location backend; py -3 -m unittest tests.test_model_provider tests.test_agent_model_status -v`

Expected: import failure for `surveyor.model_provider`.

- [ ] **Step 3: Extract the existing inline provider call without retaining the root-only credential fallback**

```python
class ModelUnavailable(RuntimeError):
    pass

class ModelFailure(RuntimeError):
    pass

def configuration() -> dict:
    base_url = os.environ.get("LLM_BASE_URL", "").strip()
    model = os.environ.get("LLM_MODEL", "").strip()
    key = os.environ.get("LLM_KEY", "").strip()
    if not base_url or not model or not key:
        raise ModelUnavailable("Cordia Agent is not configured.")
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ModelUnavailable("Cordia Agent provider configuration is invalid.")
    return {"base_url": base_url, "model": model, "key": key}
```

`call` must preserve the existing fixed OpenAI-compatible request, cap prompt fields, cap response bytes to 256 KiB, use a 30-second timeout, reject redirects to a different origin, and translate every provider/network/shape failure to the fixed public `ModelFailure("Cordia Agent could not complete that request.")` without logging request bodies, keys, or provider response text.

- [ ] **Step 4: Replace `llm.py` mock fallback with explicit availability truth**

```python
def status() -> dict:
    try:
        config = model_provider.configuration()
    except model_provider.ModelUnavailable:
        return {"available": False, "mode": "unavailable",
                "message": "Cordia Agent is not configured."}
    return {"available": True, "mode": "configured", "model": config["model"]}

def call(system: str, user: str, max_tokens: int = 900) -> str:
    return model_provider.call(system, user, max_tokens=max_tokens)
```

Remove `_llm_config`, `nous_key`, and inline `call_llm` from `training_backend.py`. Do not read `/root/.hermes/auth.json`. Do not call `surveyor.mock.call` from the workspace agent path.

- [ ] **Step 5: Add route-level honest failure tests**

```python
def test_workspace_agent_reports_unavailable_without_storing_a_run(self):
    self.provider.call.side_effect = model_provider.ModelUnavailable(
        "Cordia Agent is not configured.")
    response, status = self.post_run("workspace-1", "Connect my service")
    self.assertEqual(status, 503)
    self.assertEqual(response,
                     {"ok": False, "error": "Cordia Agent is not configured.",
                      "kind": "model_unavailable"})
    self.assertEqual(self.store.run_writes, [])
    self.assertEqual(self.store.workspace_writes, [])
```

- [ ] **Step 6: Run provider and existing model-adjacent tests**

Run: `Set-Location backend; py -3 -m unittest tests.test_model_provider tests.test_agent_model_status tests.test_runtime_config -v`

Expected: all tests pass; no assertion accepts mock speech as a successful Cordia Agent turn.

- [ ] **Step 7: Commit the provider extraction**

```powershell
git add backend/surveyor/model_provider.py backend/surveyor/llm.py backend/surveyor/__init__.py backend/training_backend.py backend/tests/test_model_provider.py backend/tests/test_agent_model_status.py
git commit -m "feat: add honest Cordia Agent provider"
```

### Task 4: Five-Envelope Cordia Agent and Workspace Turn

**Files:**
- Create: `backend/surveyor/cordia_agent.py`
- Modify: `backend/surveyor/__init__.py`
- Modify: `backend/surveyor/store.py`
- Modify: `backend/surveyor/workspace_state.py`
- Modify: `backend/training_backend.py`
- Modify: `dashboard-app/src/api.js`
- Modify: `dashboard-app/src/workspace-view.js`
- Modify: `dashboard-app/src/WorkspaceView.jsx`
- Create: `backend/tests/test_cordia_agent.py`
- Create: `backend/tests/test_workspace_turn_route.py`
- Modify: `dashboard-app/test/api.test.js`
- Create: `dashboard-app/test/agent-turn.test.js`

**Interfaces:**
- Consumes: `source/memory.md`, owner-scoped workspace state, bounded recent conversation, `surveyor.llm.call`, and exact workspace revision.
- Produces: `validate_turn_request(value: object) -> dict`, `validate_envelope(value: object) -> dict`, `build_context(memory: str, workspace: dict, recent_turns: list[dict]) -> dict`, `apply_proposal(workspace: dict, envelope: dict) -> tuple[dict, dict]`, `run_turn(context: dict, message: str, call_model: Callable) -> dict`, `POST /surveyor/run` body `{id, revision, message, idempotency_key}`, and safe public response `{ok, speech, action, revision}`.

- [ ] **Step 1: Write exact-envelope RED tests**

```python
def test_speak_is_the_only_actionless_envelope(self):
    self.assertEqual(cordia_agent.validate_envelope(
        {"kind": "speak", "speech": "What should we connect first?"}),
        {"kind": "speak", "speech": "What should we connect first?"})

def test_every_unknown_or_extra_field_fails_closed(self):
    for value in (
        {"kind": "shell", "command": "rm -rf /"},
        {"kind": "speak", "speech": "Hello", "connector": "github"},
        {"kind": "propose_connector", "speech": "Connect it", "proposal":
            {"connector_id": "drive", "setup_kind": "oauth"}},
    ):
        with self.assertRaises(ValueError):
            cordia_agent.validate_envelope(value)
```

Define exact proposal shapes in the implementation:

```python
_ACTION_FIELDS = {
    "speak": {"kind", "speech"},
    "propose_connector": {"kind", "speech", "proposal"},
    "create_artifact": {"kind", "speech", "proposal"},
    "propose_skill": {"kind", "speech", "proposal"},
    "run_approved_skill": {"kind", "speech", "proposal"},
}
_PROPOSAL_FIELDS = {
    "propose_connector": {"connector_id", "display_name", "setup_kind", "purpose"},
    "create_artifact": {"artifact_id", "title", "view_mode", "summary"},
    "propose_skill": {"skill_id", "name", "purpose", "connector_id",
                      "operation_id", "artifact_id"},
    "run_approved_skill": {"skill_id"},
}
```

- [ ] **Step 2: Run validator tests and confirm RED**

Run: `Set-Location backend; py -3 -m unittest tests.test_cordia_agent -v`

Expected: import failure for `surveyor.cordia_agent`.

- [ ] **Step 3: Implement strict JSON extraction and bounded prompt construction**

```python
def run_turn(context: dict, message: str, call_model) -> dict:
    system = build_system_prompt(context)
    raw = call_model(system, message, max_tokens=700)
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise InvalidAgentResponse("Cordia Agent returned an invalid action.") from exc
    return validate_envelope(parsed)
```

`build_system_prompt` may include only the compiled memory text, workspace title/description, safe artifact summaries, declared connector records without secret refs, declared skill summaries, and the five JSON schemas. It excludes raw profile JSON, provider payloads, permission reasons, event payloads, local paths, secret refs, ciphertext, and arbitrary workspace fields.

- [ ] **Step 4: Add canonical workspace revision and idempotent turn storage**

Extend `workspace_state.empty()` with integer `revision: 0` and `pending_actions: []`. Every accepted mutation increments exactly once. Add these idempotent existing-schema migrations, then implement:

```sql
ALTER TABLE surveyor_runs ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS surveyor_runs_owner_workspace_key_idx
ON surveyor_runs(email, interface_id, idempotency_key)
WHERE idempotency_key IS NOT NULL;
```

```python
def get_run_by_idempotency(email: str, workspace_id: str, key: str) -> dict | None:
    with _conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT meta FROM surveyor_runs WHERE email=%s AND interface_id=%s "
                       "AND idempotency_key=%s", (email, workspace_id, key))
        row = cursor.fetchone()
    return deepcopy(row[0]) if row and isinstance(row[0], dict) else None

def recent_workspace_turns(email: str, workspace_id: str, limit: int = 12) -> list[dict]:
    bounded = max(1, min(int(limit), 12))
    with _conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT input,output FROM surveyor_runs "
                       "WHERE email=%s AND interface_id=%s ORDER BY id DESC LIMIT %s",
                       (email, workspace_id, bounded))
        rows = cursor.fetchall()
    return [{"user": str(row[0] or "")[:6000],
             "assistant": str(row[1] or "")[:4000]}
            for row in reversed(rows)]

def commit_workspace_turn(email: str, workspace_id: str, expected_revision: int,
                          key: str, user_message: str, public_result: dict,
                          next_state: dict) -> dict:
    """Lock the owner row, return a prior idempotent result, or save run and state once."""
    with _conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT state FROM surveyor_workspaces "
                       "WHERE id=%s AND email=%s FOR UPDATE", (workspace_id, email))
        row = cursor.fetchone()
        if not row:
            return {"status": "missing"}
        cursor.execute("SELECT meta FROM surveyor_runs WHERE email=%s AND interface_id=%s "
                       "AND idempotency_key=%s", (email, workspace_id, key))
        prior = cursor.fetchone()
        if prior:
            return {"status": "prior", "result": prior[0]}
        if int((row[0] or {}).get("revision", 0)) != expected_revision:
            return {"status": "conflict"}
        cursor.execute("UPDATE surveyor_workspaces SET state=%s, "
                       "updated=(now() AT TIME ZONE 'utc') WHERE id=%s AND email=%s",
                       (_J(next_state), workspace_id, email))
        cursor.execute("INSERT INTO surveyor_runs"
                       "(interface_id,email,input,output,meta,idempotency_key) "
                       "VALUES(%s,%s,%s,%s,%s,%s)",
                       (workspace_id, email, user_message,
                        str(public_result.get("speech") or ""),
                        _J(public_result), key))
    return {"status": "committed", "result": public_result}
```

Only bounded user message and safe public result are stored; raw prompts/model output are not.

- [ ] **Step 5: Replace `/surveyor/run` with the exact turn contract**

The route sequence is fixed:

```python
email, stop = self._surv_guard()
if stop:
    return
try:
    request = surveyor.cordia_agent.validate_turn_request(body)
except ValueError as exc:
    self._json({"ok": False, "error": str(exc)}, 400)
    return
workspace = surveyor.store.get_workspace(email, request["id"])
if not workspace:
    self._json({"ok": False, "error": "workspace not found"}, 404)
    return
prior = surveyor.store.get_run_by_idempotency(
    email, request["id"], request["idempotency_key"])
if prior:
    self._json(prior)
    return
artifacts = surveyor.store.get_artifacts(email) or {}
memory = str(artifacts.get("source/memory.md") or "")
recent = surveyor.store.recent_workspace_turns(email, request["id"])
context = surveyor.cordia_agent.build_context(memory, workspace, recent)
envelope = surveyor.cordia_agent.run_turn(context, request["message"],
                                          surveyor.llm.call)
next_workspace, public = surveyor.cordia_agent.apply_proposal(workspace, envelope)
commit = surveyor.store.commit_workspace_turn(
    email, request["id"], request["revision"], request["idempotency_key"],
    request["message"], public, next_workspace)
if commit["status"] == "missing":
    self._json({"ok": False, "error": "workspace not found"}, 404)
    return
if commit["status"] == "conflict":
    self._json({"ok": False, "error": "workspace changed; reload and retry"}, 409)
    return
self._json(commit["result"])
```

`speak` stores no action and does not change revision. `propose_connector`, `create_artifact`, and `propose_skill` append one allow-listed record to `workspace.pending_actions` and increment revision once; they do not mark a connector available, create provider-backed data, or register an executable skill. `run_approved_skill` returns `action.state = "approval_required"` unless the named skill is already ALLOW and the request includes a separate valid approval/confirmation created by deterministic code. This task does not execute connector operations.

When a workspace has no stored turns, the renderer shows the fixed truthful greeting `I have your saved profile calibration and workspace memory. What would you like to accomplish?` only if `source/memory.md` exists; otherwise it shows `What would you like to accomplish?`. The first model-authored content still comes only from a successful real `/surveyor/run` call.

- [ ] **Step 6: Add the browser request and controller RED tests**

```javascript
test('postRun sends the exact revisioned idempotent turn contract', async () => {
  await postRun('workspace-1', 4, 'Connect my issue tracker', 'turn-abc123')
  assert.deepEqual(JSON.parse(fetchCall.options.body), {
    id: 'workspace-1', revision: 4,
    message: 'Connect my issue tracker', idempotency_key: 'turn-abc123',
  })
})

test('a proposed connector renders a setup action without claiming connected', async () => {
  const next = agentTurnModel({ok: true, speech: 'I can set that up.', revision: 5,
    action: {kind: 'propose_connector', state: 'setup_required',
             connector_id: 'issue_tracker', setup_kind: 'api_key'}})
  assert.equal(next.action.label, 'Set up issue tracker')
  assert.equal(JSON.stringify(next).includes('Connected'), false)
})
```

- [ ] **Step 7: Implement one continuous assistant interaction in the existing workspace**

Change `postRun` to the four-argument contract. The existing left Assistant submits to it, records only safe speech, renders at most one action card, and triggers exactly one canonical workspace refresh if `revision` increases. The primary route remains `/dashboard/?workspace=<id>`; do not add a new agent page.

- [ ] **Step 8: Run the Sprint 2 contract and UI suites**

Run: `Set-Location backend; py -3 -m unittest tests.test_model_provider tests.test_cordia_agent tests.test_workspace_turn_route -v`

Run: `Set-Location dashboard-app; npm.cmd test -- --test-name-pattern="agent|postRun|workspace"`

Expected: all listed tests pass. Route tests must invoke `H.do_POST`; rendered tests must click the production Assistant control.

- [ ] **Step 9: Perform the real-provider evidence gate**

With `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_KEY` configured through the approved secret channel, start the actual backend and submit one authenticated `speak` turn through `POST /surveyor/run`. Record only timestamp, model identifier, HTTP status, returned envelope kind, and workspace revision in `docs/evidence/cordia-thin-spine-real-provider.md`. Do not record the key, prompt, provider body, or assistant content.

Expected: the production route returns `200`, `kind=speak`, and no mock/limited flag. If it does not, label this gate `Not yet verified` and do not change tests to simulate success.

- [ ] **Step 10: Commit the agent-turn slice**

```powershell
git add backend/surveyor/cordia_agent.py backend/surveyor/__init__.py backend/surveyor/store.py backend/surveyor/workspace_state.py backend/training_backend.py backend/tests/test_cordia_agent.py backend/tests/test_workspace_turn_route.py dashboard-app/src/api.js dashboard-app/src/workspace-view.js dashboard-app/src/WorkspaceView.jsx dashboard-app/test/api.test.js dashboard-app/test/agent-turn.test.js docs/evidence/cordia-thin-spine-real-provider.md
git commit -m "feat: run Cordia Agent turns in one workspace"
```

## Sprint 3 — Connector, Skill, and Artifact Loop

### Task 5: Universal Connector Setup Contract

**Files:**
- Create: `backend/surveyor/connector_runtime.py`
- Modify: `backend/surveyor/__init__.py`
- Modify: `backend/surveyor/store.py`
- Modify: `backend/surveyor/workspace_state.py`
- Modify: `backend/training_backend.py`
- Modify: `dashboard-app/src/api.js`
- Modify: `dashboard-app/src/workspace-view.js`
- Modify: `dashboard-app/src/WorkspaceView.jsx`
- Create: `backend/tests/test_connector_runtime.py`
- Create: `backend/tests/test_connector_setup_route.py`
- Create: `dashboard-app/test/connector-setup.test.js`

**Interfaces:**
- Consumes: a validated `propose_connector` action, existing Fernet vault, owner-scoped workspace, and fixed server configuration.
- Produces: `validate_manifest(value: object) -> dict`, `probe(manifest: dict, credential: str | None, opener: Callable) -> dict`, `store.save_connector_records(email, records)`, and `POST /surveyor/connector/setup`.

- [ ] **Step 1: Write conformance RED tests for all three setup kinds**

```python
def test_api_key_manifest_allows_one_fixed_bounded_probe(self):
    manifest = connector_runtime.validate_manifest({
        "connector_id": "status_api", "display_name": "Status API",
        "setup_kind": "api_key", "base_url": "https://status.example.test",
        "test": {"method": "GET", "path": "/v1/me",
                 "auth": {"kind": "bearer"}},
        "operations": [{"id": "list_incidents", "method": "GET",
                        "path": "/v1/incidents", "result": "items"}],
        "live_view": False,
    })
    self.assertEqual(manifest["connector_id"], "status_api")

def test_openapi_and_remote_mcp_require_https_and_fixed_origins(self):
    for value in (OPENAPI_MANIFEST, REMOTE_MCP_MANIFEST):
        self.assertEqual(connector_runtime.validate_manifest(value)["setup_kind"],
                         value["setup_kind"])
    for bad_url in ("http://private.test", "file:///etc/passwd",
                    "https://user:pass@example.test"):
        with self.assertRaises(ValueError):
            connector_runtime.validate_manifest(
                {**OPENAPI_MANIFEST, "openapi_url": bad_url})
```

- [ ] **Step 2: Run connector tests and confirm RED**

Run: `Set-Location backend; py -3 -m unittest tests.test_connector_runtime -v`

Expected: import failure for `surveyor.connector_runtime`.

- [ ] **Step 3: Implement a small closed connector schema**

Use one record shape for stored connectors:

```python
ConnectorRecord = {
    "connector_id": str,
    "display_name": str,
    "setup_kind": Literal["api_key", "openapi", "remote_mcp"],
    "status": Literal["setup_required", "testing", "available", "needs_attention"],
    "manifest": dict,
    "secret_ref": str | None,
    "capabilities": list[str],
    "supports_live_view": bool,
    "live_view_enabled": bool,
    "last_checked_at": str | None,
}
```

Allow only HTTPS public hosts; reject loopback, link-local, RFC1918, `.local`, IP-literal private ranges, userinfo, fragments, redirects to a different origin, and response bodies over 256 KiB. API/OpenAPI executable operations are `GET` only; setup probes and MCP protocol calls may use fixed protocol-required `POST`; paths are manifest-owned; timeouts are 10 seconds; result selectors are single safe top-level keys, not arbitrary expressions.

- [ ] **Step 4: Extend the existing connector-preference row instead of adding another table**

Add the idempotent migration `ALTER TABLE surveyor_connector_preferences ADD COLUMN IF NOT EXISTS connector_records JSONB NOT NULL DEFAULT '{}'::jsonb;`, with:

```python
def get_connector_records(email: str) -> dict:
    with _conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT connector_records FROM surveyor_connector_preferences "
                       "WHERE email=%s", (email,))
        row = cursor.fetchone()
    return deepcopy(row[0]) if row and isinstance(row[0], dict) else {}

def save_connector_records(email: str, records: dict) -> None:
    with _conn() as connection, connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO surveyor_connector_preferences(email, connector_records)
            VALUES (%s,%s)
            ON CONFLICT (email) DO UPDATE SET
                connector_records=EXCLUDED.connector_records,
                updated=(now() AT TIME ZONE 'utc')
        """, (email, _J(records)))
```

The stored value contains encrypted opaque `secret_ref` only. The existing `connector_states` remains the permission/readiness projection used by `permissions.decide`.

- [ ] **Step 5: Write the route RED test for secret ordering and truthful availability**

```python
def test_setup_seals_before_probe_and_marks_available_only_after_real_success(self):
    response, status = self.post_setup(
        workspace_id="workspace-1", revision=2,
        manifest=API_KEY_MANIFEST, credential="sentinel-provider-key")
    self.assertEqual(status, 200)
    self.assertEqual(response["connector"], {
        "connector_id": "status_api", "display_name": "Status API",
        "setup_kind": "api_key", "status": "available",
        "capabilities": ["connector.status_api.list_incidents"],
        "supports_live_view": False, "live_view_enabled": False,
    })
    self.assertEqual(self.trace,
                     ["validate", "seal", "save-secret", "probe", "save-record",
                      "save-workspace"])
    self.assertNotIn("sentinel-provider-key", repr(response) + repr(self.events))
```

- [ ] **Step 6: Implement fixed setup orchestration**

`POST /surveyor/connector/setup` accepts exactly `{workspace_id, revision, manifest, credential}`. It owner-loads the workspace, checks revision, validates the manifest, seals a required credential before probing, performs the bounded real probe, saves `status=available` only after success, updates canonical connector state and workspace projection, logs only connector ID/setup kind/status, and returns the safe connector projection plus the new revision. Failure stores no raw credential and returns a fixed recovery message.

For `openapi`, the setup fetches and validates the OpenAPI JSON document and stores a bounded normalized manifest; it does not call an operation. For `remote_mcp`, the setup performs an authenticated MCP `initialize` request and requires a valid protocol response. OAuth proposals return `409` with `OAuth setup is not available for this connector yet.`

- [ ] **Step 7: Add and implement the production setup card**

```javascript
test('the production setup card sends the credential once and never stores it in state', async () => {
  const rendered = create(<ConnectorSetupCard proposal={proposal}
    onSubmit={submit} workspaceId="workspace-1" revision={2} />)
  await act(() => rendered.root.findByProps({type: 'submit'}).props.onClick())
  assert.equal(submit.calls.length, 1)
  assert.equal(JSON.stringify(rendered.toJSON()).includes('sentinel-provider-key'), false)
})
```

Add `postConnectorSetup` as one fixed request. For `api_key`, the card asks for display name, HTTPS base URL, credential, test path, one read path, and one top-level result key; deterministic code constructs the manifest and permits only GET for the executable read. For `openapi`, it asks for display name, HTTPS OpenAPI JSON URL, and optional credential. For `remote_mcp`, it asks for display name, HTTPS MCP endpoint, and credential. It clears the credential input after submission, never writes it to transcript/localStorage/workspace state, and triggers one canonical refresh.

- [ ] **Step 8: Run connector contract, route, and rendered tests**

Run: `Set-Location backend; py -3 -m unittest tests.test_connector_runtime tests.test_connector_setup_route tests.test_vault tests.test_capability_gateway -v`

Run: `Set-Location dashboard-app; npm.cmd test -- --test-name-pattern="connector setup|postConnectorSetup"`

Expected: all tests pass; route tests invoke `H.do_POST`; rendered tests operate the production setup card.

- [ ] **Step 9: Commit the universal connector contract**

```powershell
git add backend/surveyor/connector_runtime.py backend/surveyor/__init__.py backend/surveyor/store.py backend/surveyor/workspace_state.py backend/training_backend.py backend/tests/test_connector_runtime.py backend/tests/test_connector_setup_route.py dashboard-app/src/api.js dashboard-app/src/workspace-view.js dashboard-app/src/WorkspaceView.jsx dashboard-app/test/connector-setup.test.js
git commit -m "feat: add universal connector setup"
```

### Task 6: Declarative Generated Skill and Evidence-Backed Artifact Update

**Files:**
- Modify: `backend/surveyor/skills.py`
- Modify: `backend/surveyor/capability_gateway.py`
- Modify: `backend/surveyor/permissions.py`
- Modify: `backend/surveyor/workspace_state.py`
- Modify: `backend/training_backend.py`
- Modify: `dashboard-app/src/api.js`
- Modify: `dashboard-app/src/workspace-view.js`
- Modify: `dashboard-app/src/WorkspaceView.jsx`
- Create: `backend/tests/test_generated_skill.py`
- Create: `backend/tests/test_generated_skill_route.py`
- Modify: `backend/tests/test_permissions.py`
- Modify: `dashboard-app/test/skill-interaction.test.js`
- Modify: `dashboard-app/test/workspace-view.test.js`

**Interfaces:**
- Consumes: one `available` connector record, a validated `propose_skill` envelope, existing ALLOW/ASK/DENY gateway, and one declared operation.
- Produces: `validate_generated_skill(value: object, connector_record: dict) -> dict`, `execute_generated_skill(skill: dict, connector_record: dict, connector_states: dict, operation: Callable) -> dict`, and a canonical artifact window with provenance.

- [ ] **Step 1: Write skill validation RED tests**

```python
def test_generated_skill_binds_to_one_declared_connector_operation_and_artifact(self):
    skill = skills.validate_generated_skill({
        "id": "review_incidents", "name": "Review incidents",
        "purpose": "Show current incidents in the workspace.",
        "connector_id": "status_api", "operation_id": "list_incidents",
        "permission": "ALLOW", "artifact": {
            "id": "status-incidents", "title": "Current incidents",
            "view_mode": "dash", "projection": "list",
        },
    }, CONNECTOR_RECORD)
    self.assertEqual(skill["operation_id"], "list_incidents")

def test_generated_skill_rejects_code_urls_prompts_secrets_and_unknown_fields(self):
    for forbidden_key in ("code", "url", "prompt", "secret", "shell", "headers"):
        with self.assertRaises(ValueError):
            skills.validate_generated_skill({**VALID_SKILL, forbidden_key: "hidden"},
                                            CONNECTOR_RECORD)
```

- [ ] **Step 2: Run generated-skill tests and confirm RED**

Run: `Set-Location backend; py -3 -m unittest tests.test_generated_skill -v`

Expected: `validate_generated_skill` does not exist.

- [ ] **Step 3: Add workspace-scoped generated skills without creating another registry**

Store generated skill manifests in canonical `workspace["skills"]`. Built-in skills still resolve from `_SKILLS`; generated execution receives the owner-loaded workspace skill and validates it against the current connector record every time. Add a dynamic gateway call:

```python
def execute_declared(capability: dict, connector_states: dict, operation) -> dict:
    validated = validate_declared_capability(capability)
    gate = permissions.decide_declared(validated, connector_states)
    if gate["decision"] != "ALLOW":
        return {"ok": False, "capability": public_capability(validated),
                "permission": gate, "error": gate["reason"]}
    return {"ok": True, "capability": public_capability(validated),
            "permission": gate, "result": operation()}
```

Add the exact declared-permission rule:

```python
def decide_declared(capability: dict, connector_states: dict | None = None) -> dict:
    connector_id = capability["connector"]
    if capability["permission"] != "ALLOW" or capability["effect"] != "read":
        return {"decision": "DENY", "reason": "This generated operation is not read-only."}
    if (connector_states or {}).get(connector_id) != "confirmed":
        return {"decision": "ASK", "reason": "Confirm the connector before Cordia reads data."}
    return {"decision": "ALLOW", "reason": "Read-only access is allowed for a confirmed connector."}
```

The capability is derived server-side from connector ID plus manifest operation ID. The browser/model cannot provide method, URL, headers, or secret reference during execution. Generic operations are read-only in this MVP: API/OpenAPI operations use `GET`; remote MCP tools must advertise `readOnlyHint: true`. Setup probes may use their protocol-required `POST`, but that does not make a generated write skill executable.

- [ ] **Step 4: Write the real route loop RED test**

```python
def test_run_approved_skill_updates_one_artifact_from_real_adapter_output(self):
    response, status = self.post("/surveyor/skill/execute", {
        "workspace_id": "workspace-1", "revision": 5,
        "skill_id": "review_incidents", "idempotency_key": "skill-run-1",
    })
    self.assertEqual(status, 200)
    self.assertEqual(response, {
        "ok": True, "skill_id": "review_incidents",
        "artifact_id": "status-incidents", "revision": 6,
        "result_summary": {"item_count": 2},
    })
    saved = self.store.get_workspace("owner@example.test", "workspace-1")
    window = next(item for item in saved["windows"]
                  if item["id"] == "status-incidents")
    self.assertEqual(window["data"]["items"], SAFE_PROVIDER_ITEMS)
    self.assertEqual(window["provenance"]["connector_id"], "status_api")
    self.assertNotIn("sentinel-provider-key", repr(saved) + repr(response))
```

- [ ] **Step 5: Implement the execution and artifact projection transaction**

When `apply_proposal` receives `propose_skill` after this task, it validates the proposed skill against the current `available` connector record and declared read operation, adds the safe manifest to canonical `workspace.skills`, removes the matching pending action, and increments revision once. A proposal against a missing, failed, mismatched, or write-capable operation remains non-executable with a fixed reason.

The execution route owner-loads workspace/skill/connector, checks revision/idempotency, evaluates permission before secret resolution, opens the secret only inside the ALLOW operation closure, invokes the fixed manifest operation, validates and bounds the result, creates a DashView artifact projection, increments revision once, and persists it through `store.commit_workspace_turn` using a fixed synthetic user message `Run skill <safe skill id>`. It returns only IDs/count/revision. A concurrent revision conflict or duplicate idempotency key cannot apply a second artifact mutation.

Add to `workspace_state.py`:

```python
def upsert_artifact(state: dict, artifact: dict, provenance: dict) -> dict:
    """Replace one matching agent-generated artifact or append it, then increment revision."""
```

The artifact permits at most 100 items, 20 safe fields per item, 240 characters per field, and 64 KiB total JSON. Provenance includes connector ID, operation ID, skill ID, observed timestamp, and result count—never URL, headers, secret reference, raw response, or local path.

- [ ] **Step 6: Add rendered click-to-visible-update evidence**

Change the browser API to the exact signature:

```javascript
export async function postSkillExecute(workspaceId, revision, skillId, idempotencyKey) {
  const headers = {'Content-Type': 'application/json'}
  const devToken = localStorage.getItem('cordia-dev-token')
  if (devToken) headers.Authorization = `Bearer ${devToken}`
  return validatedRequest('/surveyor/skill/execute', {
    method: 'POST', headers, credentials: 'include',
    body: JSON.stringify({workspace_id: workspaceId, revision, skill_id: skillId,
                          idempotency_key: idempotencyKey}),
  })
}
```

Extend the production skill interaction test so clicking the generated skill executes exactly once, receives the safe receipt, performs exactly one canonical refresh, and the refreshed `WorkspaceCanvas` renders the new `Current incidents` artifact with the two safe rows. A failed provider response must leave the old artifact and revision unchanged and render a bounded recovery message.

- [ ] **Step 7: Run the complete connector/skill/artifact loop tests**

Run: `Set-Location backend; py -3 -m unittest tests.test_connector_runtime tests.test_connector_setup_route tests.test_generated_skill tests.test_generated_skill_route tests.test_capability_gateway tests.test_permissions tests.test_vault -v`

Run: `Set-Location dashboard-app; npm.cmd test -- --test-name-pattern="skill|artifact|workspace"`

Expected: all tests pass. The route integration must call the production connector runtime with a deterministic HTTP double; this is Verified locally, not Verified with real provider.

- [ ] **Step 8: Perform one real non-GitHub connector evidence gate**

Use the production setup card to configure one real API-key, OpenAPI, or remote-MCP connector. Through the production workspace, ask the Cordia Agent to propose the connector, complete setup, register a declarative skill, click the skill, and observe the resulting artifact. Record only connector setup kind, safe connector ID, skill ID, artifact ID, final workspace revision, timestamps, and pass/fail in `docs/evidence/cordia-thin-spine-real-connector.md`.

Expected: the real connector probe succeeds, the skill uses the same stored connector record/gateway/vault path, and the artifact changes after execution. Otherwise record `Not yet verified`; do not substitute GitHub or a fake adapter for the required non-GitHub evidence.

- [ ] **Step 9: Commit the working connector loop**

```powershell
git add backend/surveyor/skills.py backend/surveyor/capability_gateway.py backend/surveyor/permissions.py backend/surveyor/workspace_state.py backend/training_backend.py backend/tests/test_generated_skill.py backend/tests/test_generated_skill_route.py backend/tests/test_permissions.py dashboard-app/src/api.js dashboard-app/src/workspace-view.js dashboard-app/src/WorkspaceView.jsx dashboard-app/test/skill-interaction.test.js dashboard-app/test/workspace-view.test.js docs/evidence/cordia-thin-spine-real-connector.md
git commit -m "feat: turn connector results into workspace artifacts"
```

## Sprint 4 — Continuous Journey and Release Candidate

### Task 7: One Actual-App Journey, Recovery, and Evidence Reconciliation

**Files:**
- Modify: `web/index.html`
- Modify: `dashboard-app/src/App.jsx`
- Modify: `dashboard-app/src/WorkspaceView.jsx`
- Modify: `dashboard-app/src/app.css`
- Create: `backend/tests/test_thin_spine_journey.py`
- Create: `dashboard-app/test/thin-spine-journey.test.js`
- Create: `docs/LIVE_SETUP_AND_TEST_MANUAL.md`
- Modify: `docs/TODO_CORDIA_VERTICAL_SLICE.md`
- Modify: `backend/SURVEYOR_RUNTIME_SETUP.md`
- Regenerate: `web/dashboard/index.html`
- Regenerate: `web/dashboard/assets/*`

**Interfaces:**
- Consumes: every production route and UI contract from Tasks 1–6.
- Produces: one uninterrupted actual-app user journey, a reproducible dashboard bundle, an operator test manual, and evidence-accurate authority docs.

- [ ] **Step 1: Write a backend journey test that uses the HTTP handler and production modules**

```python
def test_new_owner_reaches_an_updated_saved_workspace(self):
    self.authenticate("owner@example.test")
    imported = self.post_profile_calibration(VALID_PROFILE)
    workspace_id = imported["workspace_id"]
    turn = self.post_turn(workspace_id, revision=0,
                          message="Connect my status service",
                          idempotency_key="turn-1")
    self.assertEqual(turn["action"]["kind"], "propose_connector")
    connected = self.post_connector_setup(workspace_id, turn["revision"],
                                          REAL_SHAPED_MANIFEST, "sentinel-key")
    skill = self.post_turn(workspace_id, connected["revision"],
                           "Show current incidents", "turn-2")
    executed = self.post_skill(workspace_id, skill["revision"],
                               skill["action"]["skill_id"], "skill-1")
    recovered = self.get_workspace_as("owner@example.test", workspace_id)
    self.assertEqual(recovered["revision"], executed["revision"])
    self.assertTrue(any(window["id"] == executed["artifact_id"]
                        for window in recovered["windows"]))
```

This test uses a deterministic model double and deterministic external HTTP double only at their explicit network seams. It must use real production validators, HTTP routes, store behavior, vault encryption, gateway, workspace mutation, and response render models. Its evidence label is Verified locally only.

- [ ] **Step 2: Write production React journey and reload tests**

The rendered test must drive production controls in order: submit a Cordia Agent message, open connector setup, submit one credential, click the proposed skill, see an artifact card, unmount/remount with the same workspace ID, and see the same card from canonical reload. It must also prove model failure, connector failure, revision conflict, duplicate idempotency key, sign-out, and sign-in recovery without fabricated success.

- [ ] **Step 3: Remove visible compatibility handoffs from new-user navigation**

New sign-in/profile completion paths may link only to the external survey or `/dashboard/?workspace=<safe-id>`. The primary workspace may not link the user to `surveyor.html`, `builder.html`, or `interface.html`. Keep those files/routes intact for compatibility, but add no new references to them.

- [ ] **Step 4: Complete the reference workspace layout without adding unsupported features**

Keep the Cordia Agent fixed on the left and artifact windows on the right. Render connector setup and approval states as cards in this same surface. Preserve the existing Cordia ivory/sage visual system and inspection dock. Do not render fake Google Drive, Notion, Hostinger, Discord, Mercury, automation, LiveView, or enterprise data merely to resemble the reference image.

- [ ] **Step 5: Run all repository test suites before building**

Run: `Set-Location backend; py -3 -m unittest discover -s tests -v`

Run: `Set-Location web; node --test test/*.test.js`

Run: `Set-Location dashboard-app; npm.cmd ci; npm.cmd test`

Run: `Set-Location desktop; npm.cmd ci; npm.cmd test`

Expected: every suite passes. If an environment dependency prevents a suite from starting, record the exact import/tool failure as unresolved; do not report the suite as passed.

- [ ] **Step 6: Build and verify the packaged dashboard**

Run: `Set-Location dashboard-app; npm.cmd run build`

Run: `Set-Location ..\desktop; npm.cmd run verify:dashboard-release`

Expected: Vite completes, `web/dashboard/index.html` references the newly generated hashed assets, and the desktop release verifier reproduces the committed bundle from the committed source.

- [ ] **Step 7: Execute the local actual-app acceptance journey**

Start the real backend with a test database, real model configuration, and one approved real non-GitHub connector credential. Open the actual site in the in-app browser and complete the acceptance path through production pages and controls. Capture screenshots at: profile completion return, first workspace, connector setup required, connector available, proposed skill, and updated artifact after reload. Save them under `docs/evidence/thin-spine-local/` and write a `README.md` containing timestamp, commit SHA, evidence labels, and any failed step.

- [ ] **Step 8: Write the live setup and test manual using exact operator actions**

`docs/LIVE_SETUP_AND_TEST_MANUAL.md` must list required environment variables, database migration/preflight, backend service restart, static dashboard deployment, health check, real-model check, survey callback check, real-connector check, artifact update/reload check, and rollback commit. It must state that GitHub catalog visibility, unit tests, a build, or a localhost screenshot do not prove the public journey is live.

- [ ] **Step 9: Reconcile authority docs from evidence, not intention**

Update `docs/TODO_CORDIA_VERTICAL_SLICE.md` only for requirements directly demonstrated by committed source plus the recorded route/UI evidence. Label external survey, real model, real connector, desktop, and production separately. Leave unsupported OAuth, LiveView, Alidora execution, billing, and public deployment unchecked.

- [ ] **Step 10: Run final static and privacy checks**

Run: `git diff --check`

Run: `rg -n "sentinel|BEGIN PRIVATE KEY|LLM_KEY|CORDIA_PROFILE_API_TOKEN|secret_ref|ciphertext" web/dashboard docs/evidence`

Expected: diff check exits 0; the secret scan finds only explanatory field names in documentation and no credential values, ciphertext, provider payloads, or test sentinels in release assets/evidence.

- [ ] **Step 11: Request independent whole-branch review**

Review `origin/main..HEAD` against the approved design and this plan. The reviewer must specifically verify owner isolation, honest model failure, exact action schemas, credential ordering, SSRF controls, permission-before-secret ordering, idempotency/revision behavior, artifact provenance, rendered continuity, and evidence-label truth. Any Critical or Important finding receives its own RED/GREEN fix cycle and separate commit.

- [ ] **Step 12: Commit the release-candidate slice**

```powershell
git add web/index.html dashboard-app/src/App.jsx dashboard-app/src/WorkspaceView.jsx dashboard-app/src/app.css backend/tests/test_thin_spine_journey.py dashboard-app/test/thin-spine-journey.test.js docs/LIVE_SETUP_AND_TEST_MANUAL.md docs/TODO_CORDIA_VERTICAL_SLICE.md backend/SURVEYOR_RUNTIME_SETUP.md web/dashboard
git commit -m "feat: complete the Cordia thin-spine journey"
```

- [ ] **Step 13: Stop at the release authorization boundary**

Report the exact commit SHA and evidence matrix. Do not push, merge, or deploy unless the product owner explicitly authorizes that action. After authorization, use the repository's branch/PR process and Hostinger hPanel VPS Web Console; verify backend health and the public sign-in-to-artifact journey before using the label `Verified live`.

## Final Evidence Matrix

| Outcome | Minimum evidence | Forbidden substitute |
|---|---|---|
| Profile contract built | strict validator + route tests | screenshot of external survey |
| External survey integrated | actual provider callback/result retrieval through Cordia | pasted sample payload |
| Cordia Agent built | strict action/parser tests + production route | direct helper call |
| Real model verified | configured production route returns a valid envelope | fake opener or mock speech |
| Connector contracts built | API-key/OpenAPI/MCP conformance tests | catalog entries |
| Real connector verified | production setup/skill/artifact path against non-GitHub service | deterministic adapter or GitHub |
| Workspace continuity verified | rendered actual-app path plus reload | component snapshot alone |
| Release built | clean full suites + reproducible committed bundle | source-only green test |
| Public MVP live | direct public journey after authorized deploy | merged code, server restart, or health check alone |
