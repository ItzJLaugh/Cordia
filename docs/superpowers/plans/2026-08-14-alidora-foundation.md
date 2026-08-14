# Alidora Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Alidora — Agentic System Builder by Cordia as an authenticated, read-only System Map of Cordia's existing canonical workspace.

**Architecture:** `surveyor.workspace_state` stays the only state owner. A pure `surveyor.alidora` module projects a safe map; an authenticated GET route returns it; Mason's React Flow dashboard renders it without editing, execution, connector setup, or approval actions.

**Tech Stack:** Python standard-library HTTP, Surveyor/store/workspace contracts, React, Vite, `@xyflow/react`.

**Spec:** `docs/ALIDORA_INTEGRATION_CHARTER.md`

## Global Constraints

- Alidora adds no graph-owned state, registry, gateway, permission engine, execution route, secret path, or outcome loop.
- Its only new API is authenticated and read-only: `GET /surveyor/alidora/map?id=<workspace_id>`.
- Payloads exclude raw profile/artifact text, context-source values, mutations, provenance payloads, secrets, credentials, and local paths.
- Cordia Workspace remains chat-first; Alidora is an advanced tab.
- Use TDD, `npm.cmd`, and `C:\Users\jacks\AppData\Local\Programs\Python\Python312\python.exe` when `python`/`py` is unavailable.

## Files

- Create `backend/surveyor/alidora.py`: safe deterministic canonical-workspace projection.
- Modify `backend/surveyor/__init__.py`: expose `alidora` to the current runtime facade.
- Modify `backend/training_backend.py`: GET dispatch and handler only.
- Create `backend/tests/test_alidora.py`: projection, privacy, route, auth-scope, and no-write coverage.
- Modify `dashboard-app/src/api.js`, `graph.js`, `DefinitionGraph.jsx`, `App.jsx`: safe GET and read-only React Flow map.
- Modify `web/interface.html`: discoverable non-primary Alidora entry point after build verification.
- Modify `docs/ALIDORA_INTEGRATION_CHARTER.md` and `docs/TODO_CORDIA_VERTICAL_SLICE.md`: truthful completion status.

## Contract

```python
def map_payload(workspace: dict) -> dict:
    """Return safe, deterministic workspace/map data only."""

# Returned shape
{
  "workspace": {"id": "w-1", "title": "Launch", "description": ""},
  "nodes": [{"id": "agent:review", "kind": "agent", "label": "Review", "detail": ""}],
  "edges": [],
  "summary": {"agents": 1, "skills": 0, "connectors": 0, "approval_mode": "compiled"}
}
```

---

### Task 1: Build and test the safe canonical-state projection

**Files:** Create `backend/surveyor/alidora.py`; modify `backend/surveyor/__init__.py`; create `backend/tests/test_alidora.py`.

**Consumes:** canonical `id`, `title`, `description`, `agents`, `skills`, `connectors`, `workflow`, `permissions`.

**Produces:** `alidora.map_payload(workspace)`.

- [ ] **Step 1: Write a failing projection/privacy test.**

```python
from surveyor import alidora

def test_map_payload_is_safe_and_deterministic():
    state = {"id": "w-1", "title": "Launch", "agents": [{"id": "review", "name": "Review"}], "skills": [], "connectors": [], "permissions": {"mode": "compiled"}, "context_sources": [{"id": "C:\\private\\repo"}], "provenance": [{"secret": "must-not-leak"}]}
    result = alidora.map_payload(state)
    assert result["workspace"] == {"id": "w-1", "title": "Launch", "description": ""}
    assert result["nodes"] == [{"id": "agent:review", "kind": "agent", "label": "Review", "detail": ""}]
    assert result["summary"] == {"agents": 1, "skills": 0, "connectors": 0, "approval_mode": "compiled"}
    assert "private" not in repr(result)
    assert "must-not-leak" not in repr(result)
```

- [ ] **Step 2: Run red.**

Run: `& 'C:\Users\jacks\AppData\Local\Programs\Python\Python312\python.exe' -m unittest discover -s backend/tests -p 'test_alidora.py' -v`

Expected: import failure because `surveyor.alidora` does not exist.

- [ ] **Step 3: Implement minimally.** Use allow-listed node fields, stable id ordering, and edges only where both endpoint ids were emitted. Ignore malformed entries and unresolved workflow references.

```python
def map_payload(workspace):
    state = workspace if isinstance(workspace, dict) else {}
    nodes = _nodes(state)
    return {"workspace": {key: str(state.get(key) or "") for key in ("id", "title", "description")}, "nodes": nodes, "edges": _edges(state, {node["id"] for node in nodes}), "summary": _summary(nodes, state.get("permissions"))}
```

- [ ] **Step 4: Add malformed/unresolved-reference coverage, then run green.**

```python
def test_map_payload_discards_unresolved_references():
    result = alidora.map_payload({"id": "w", "workflow": {"steps": [{"agent_id": "missing"}]}})
    assert result["nodes"] == []
    assert result["edges"] == []
```

Run: `& 'C:\Users\jacks\AppData\Local\Programs\Python\Python312\python.exe' -m unittest discover -s backend/tests -p 'test_alidora.py' -v`

- [ ] **Step 5: Commit.** Run: `git add backend/surveyor/alidora.py backend/surveyor/__init__.py backend/tests/test_alidora.py; git commit -m "feat: add safe Alidora workspace projection"`

### Task 2: Add an authenticated read-only endpoint

**Files:** Modify `backend/training_backend.py`; modify `backend/tests/test_alidora.py`.

**Consumes:** `_surv_guard()`, `store.get_workspace(email, workspace_id)`, `alidora.map_payload(state)`.

**Produces:** `GET /surveyor/alidora/map?id=<workspace_id>` returning 200, 400, or 404 only.

- [ ] **Step 1: Write failing route and scope tests.**

```python
def test_alidora_map_requires_workspace_id(authenticated_handler):
    assert authenticated_handler.get('/surveyor/alidora/map') == (400, {"ok": False, "error": "workspace id is required"})

def test_alidora_map_is_scoped_to_authenticated_user(authenticated_handler, store):
    store.save_workspace('owner@example.com', 'w-1', {"id": "w-1", "title": "Launch"})
    store.save_workspace('other@example.com', 'w-2', {"id": "w-2", "title": "Private"})
    assert authenticated_handler.get('/surveyor/alidora/map?id=w-1')[0] == 200
    assert authenticated_handler.get('/surveyor/alidora/map?id=w-2')[0] == 404
```

- [ ] **Step 2: Run red.** Run the Task 1 test command. Expected: no route dispatch/handler.

- [ ] **Step 3: Add one dispatch arm and one handler.**

```python
elif p == '/surveyor/alidora/map':
    self._surv_alidora_map()

def _surv_alidora_map(self):
    email = self._surv_guard()
    if not email: return
    workspace_id = str(parse_qs(urlparse(self.path).query).get('id', [''])[0])
    if not workspace_id:
        self._json({'ok': False, 'error': 'workspace id is required'}, 400); return
    state = surveyor.store.get_workspace(email, workspace_id)
    if not state:
        self._json({'ok': False, 'error': 'workspace not found'}, 404); return
    self._json({'ok': True, 'map': surveyor.alidora.map_payload(state)})
```

No `save_workspace`, `log_event`, vault access, `skills.execute`, or `capability_gateway.execute` call is permitted.

- [ ] **Step 4: Add a no-write regression and run green.** Monkeypatch `save_workspace` and `skills.execute` to throw; endpoint response remains 200. Run `test_alidora.py` and `test_fde_*.py`.

- [ ] **Step 5: Commit.** Run: `git add backend/training_backend.py backend/tests/test_alidora.py; git commit -m "feat: expose authenticated Alidora system map"`

### Task 3: Adapt Mason's graph renderer to the map contract

**Files:** Modify `dashboard-app/src/api.js`, `graph.js`, `DefinitionGraph.jsx`, `App.jsx`; add a test using the test runner already declared by `dashboard-app/package.json`.

**Consumes:** `map` from Task 2.

**Produces:** `alidoraMapToFlow(map)` and a read-only graph surface.

- [ ] **Step 1: Inspect `dashboard-app/package.json`; add a failing test in its installed test runner.**

```javascript
import { alidoraMapToFlow } from './graph.js'

it('converts map data without inventing editable graph state', () => {
  const flow = alidoraMapToFlow({ nodes: [{ id: 'agent:a', kind: 'agent', label: 'A', detail: '' }], edges: [] })
  expect(flow.nodes[0].id).toBe('agent:a')
  expect(flow.nodes[0].draggable).toBe(false)
  expect(flow.edges).toEqual([])
})
```

- [ ] **Step 2: Run the focused test red.** Expected: missing `alidoraMapToFlow`.

- [ ] **Step 3: Implement safe GET and rendering.**

```javascript
export async function getApi(path) {
  const response = await fetch(`${API}${path}`, { credentials: 'include' })
  const body = await response.json()
  if (!response.ok || !body.ok) throw new Error(body.error || 'Request failed')
  return body
}
```

`alidoraMapToFlow` sorts nodes, reuses Mason's deterministic geometry, maps only safe fields, and sets `draggable`, `connectable`, and `deletable` to `false`. `App.jsx` reads a `workspace` query value and renders exact loading, empty, and safe-error states. Header: `Alidora`; subtitle: `Agentic System Builder by Cordia`. No save/run/edit/execute/approval buttons.

- [ ] **Step 4: Run green and build from the correct directory.** Run: `Set-Location dashboard-app; npm.cmd test; npm.cmd run build`. If no `test` script exists, use only the installed runner shown by `package.json`.

- [ ] **Step 5: Commit.** Run: `git add dashboard-app/src dashboard-app/package.json; git commit -m "feat: render read-only Alidora system map"`

### Task 4: Link Cordia, verify shared identity, and prepare review

**Files:** Modify `web/interface.html`, `docs/ALIDORA_INTEGRATION_CHARTER.md`, `docs/TODO_CORDIA_VERTICAL_SLICE.md`, and `backend/tests/test_alidora.py`.

**Consumes:** Tasks 1–3 and the current workspace id.

**Produces:** a non-primary Alidora entry point and evidence that Cordia and Alidora see the same saved workspace.

- [ ] **Step 1: Write a failing discovery assertion.**

```python
def test_workspace_keeps_chat_default_and_exposes_alidora():
    page = Path('web/interface.html').read_text(encoding='utf-8')
    assert 'CORDIA AGENT' in page
    assert 'Alidora' in page
    assert 'Agentic System Builder' in page
```

- [ ] **Step 2: Run red.** Expected: Alidora is absent.

- [ ] **Step 3: Add the non-primary navigation item.** Label it `Alidora — Agentic System Builder`; preserve workspace id; never replace the left Cordia assistant or the default workspace surface.

- [ ] **Step 4: Add and run shared-state verification.**

```python
def test_workspace_and_alidora_map_share_identity_and_agent_count(authenticated_handler, store):
    store.save_workspace('owner@example.com', 'w-1', {"id": "w-1", "agents": [{"id": "review"}]})
    _, workspace = authenticated_handler.get('/surveyor/workspace?id=w-1')
    _, result = authenticated_handler.get('/surveyor/alidora/map?id=w-1')
    assert workspace['workspace']['id'] == result['map']['workspace']['id'] == 'w-1'
    assert len(workspace['workspace']['agents']) == result['map']['summary']['agents']
```

Run: `& 'C:\Users\jacks\AppData\Local\Programs\Python\Python312\python.exe' -m unittest discover -s backend/tests -v; Set-Location desktop; npm.cmd test; Set-Location ..\dashboard-app; npm.cmd run build; git diff --check origin/main...HEAD`

- [ ] **Step 5: Record only verified scope and commit.** Mark the read-only map complete. Explicitly defer authoring, execution, connector setup, and approval actions. Run: `git add web/interface.html docs/ALIDORA_INTEGRATION_CHARTER.md docs/TODO_CORDIA_VERTICAL_SLICE.md backend/tests/test_alidora.py; git commit -m "feat: link Cordia workspace to Alidora"`

- [ ] **Step 6: Open a draft PR.** Title: `feat: add Alidora read-only system map`. State that it does not merge an alternate execution runtime or make Alidora the default workspace surface.

## Deferred Separate Plans

1. Guarded authoring: typed graph-to-canonical-state mutations, concurrency, and Cordia approvals.
2. Operations: safe run history, traces, checkpoints, and unified audit projection.
3. Company systems: reusable templates/playbooks, validation, and controlled installation.
4. Product routing and hosting: preview deployment, production deployment, and setup manual.

## Plan Self-Review

- **Spec coverage:** Tasks 1–2 protect shared state and runtime boundaries; Task 3 captures Mason's graph strengths; Task 4 keeps Cordia chat-first and demonstrates shared state.
- **Placeholder scan:** Every task names files, contract, failing test, verification, and commit; intentionally excluded future systems are separate plans.
- **Type consistency:** Task 1 defines `map_payload`; Task 2 returns it under `map`; Task 3 consumes `map`; Task 4 compares it with `/surveyor/workspace`.
