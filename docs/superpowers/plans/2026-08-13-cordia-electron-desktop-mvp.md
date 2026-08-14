# Cordia Electron Desktop MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a Windows Electron shell that loads the user's existing cloud
workspace and exposes one explicit, read-only local repository capability.

**Architecture:** Electron's renderer loads the existing cloud application;
the preload layer exposes a fixed contextBridge API; the main process owns
native folder selection and safe Git metadata inspection. Cloud state remains
authoritative, while local selected-directory mappings remain in Electron user
data and never enter prompts or cloud storage.

**Tech Stack:** Electron, Node.js built-ins, Electron Forge or electron-builder,
existing Cordia Python capability gateway and workspace contracts.

**Spec:** `docs/superpowers/specs/2026-08-13-cordia-electron-desktop-mvp-design.md`

## Global Constraints

- Electron renderer must have `contextIsolation: true`, `nodeIntegration: false`, and no arbitrary IPC.
- Default cloud origin is `https://cordiacode.com`; localhost preview is an explicit development option.
- Cloud workspace remains authoritative; desktop stores no competing workspace copy.
- Only user-picked Git repository metadata may be surfaced; never send file content or absolute paths to cloud.
- The first local capability is read-only. Writes, shell commands, package installation, pushes, and deployment remain unavailable.
- Follow test-driven development for all behavior changes; do not add raw secrets to desktop configuration.

---

### Task 1: Create the desktop package and secure shell

**Files:**
- Create: `desktop/package.json`
- Create: `desktop/main.js`
- Create: `desktop/preload.js`
- Create: `desktop/test/main.test.js`
- Create: `desktop/README.md`

**Interfaces:**
- Produces `window.cordiaDesktop.getRuntimeInfo(): Promise<{platform:string, version:string}>`.
- `main.js` creates a BrowserWindow with context isolation, no Node integration, and an explicit target origin.

- [ ] **Step 1: Write the failing shell tests**

```js
test('creates an isolated BrowserWindow', () => {
  expect(windowOptions.webPreferences).toMatchObject({
    contextIsolation: true,
    nodeIntegration: false,
  });
});

test('preload exposes only the desktop namespace', () => {
  expect(exposedApi).toEqual({ cordiaDesktop: { getRuntimeInfo: expect.any(Function), pickRepository: expect.any(Function) } });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd desktop && npm test -- main.test.js`

Expected: FAIL because the package and secure shell do not exist.

- [ ] **Step 3: Implement the minimal secure Electron shell**

```js
const win = new BrowserWindow({
  webPreferences: { preload, contextIsolation: true, nodeIntegration: false, sandbox: true },
});
win.loadURL(process.env.CORDIA_DESKTOP_URL || 'https://cordiacode.com');
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd desktop && npm test -- main.test.js`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add desktop
git commit -m "feat: add secure Cordia Electron shell"
```

### Task 2: Add explicit read-only local repository discovery

**Files:**
- Create: `desktop/local_repository.js`
- Create: `desktop/test/local_repository.test.js`
- Modify: `desktop/main.js`
- Modify: `desktop/preload.js`

**Interfaces:**
- Produces `discoverRepository(selectedPath): {kind, id, label, path_label, git_root, branch}`.
- `pickRepository()` opens one native directory dialog and returns either `null` for cancellation or the safe metadata record.

- [ ] **Step 1: Write failing repository-discovery tests**

```js
test('rejects a selected directory without a .git directory', () => {
  expect(() => discoverRepository(nonGitDirectory)).toThrow('Select a Git repository directory.');
});

test('returns metadata without an absolute path field', () => {
  const result = discoverRepository(gitFixtureDirectory);
  expect(result).toMatchObject({ kind: 'local_repository', git_root: true });
  expect(result).not.toHaveProperty('path');
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd desktop && npm test -- local_repository.test.js`

Expected: FAIL because repository discovery does not exist.

- [ ] **Step 3: Implement fixed-path discovery with Node fs/path only**

```js
if (!fs.existsSync(path.join(selectedPath, '.git'))) throw new Error('Select a Git repository directory.');
return { kind: 'local_repository', id: opaqueId(selectedPath), label: path.basename(selectedPath), path_label: path.basename(selectedPath), git_root: true, branch };
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd desktop && npm test -- local_repository.test.js`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add desktop
git commit -m "feat: add explicit read-only local repository bridge"
```

### Task 3: Extend the shared capability model for local repository description

**Files:**
- Modify: `backend/surveyor/capability_gateway.py`
- Modify: `backend/surveyor/permissions.py`
- Create: `backend/tests/test_desktop_capability.py`

**Interfaces:**
- Adds typed capability `desktop.local_repository.describe`.
- `permissions.decide('desktop.local_repository.describe', states)` returns `ALLOW` only with explicit local repository state.

- [ ] **Step 1: Write failing capability tests**

```python
def test_allows_local_repository_metadata_only_after_explicit_desktop_selection():
    assert permissions.decide('desktop.local_repository.describe', {'desktop.local_repository': 'confirmed'})['decision'] == 'ALLOW'

def test_keeps_local_repository_writes_approval_gated():
    assert permissions.decide('desktop.local_repository.write', {'desktop.local_repository': 'confirmed'})['decision'] == 'ASK'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_desktop_capability -v`

Expected: FAIL because no desktop capability is registered.

- [ ] **Step 3: Add the typed metadata capability and permission cases**

```python
_CAPABILITIES['desktop.local_repository.describe'] = {
    'connector': 'desktop.local_repository', 'permission': 'ALLOW',
    'transport': 'local_bridge', 'summary': 'Describe a user-selected local Git repository without reading files.'}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_desktop_capability tests.test_capability_gateway -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/surveyor backend/tests/test_desktop_capability.py
git commit -m "feat: register read-only desktop repository capability"
```

### Task 4: Connect desktop selection to canonical workspace provenance

**Files:**
- Modify: `backend/surveyor/workspace_state.py`
- Modify: `backend/tests/test_workspace_state.py`
- Modify: `web/interface.html`
- Modify: `desktop/preload.js`

**Interfaces:**
- Adds an allowed `local_repository` context reference containing opaque id and label only.
- The workspace UI renders the local-selection request only if `window.cordiaDesktop` exists.

- [ ] **Step 1: Write the failing canonical-state test**

```python
def test_adds_local_repository_context_without_absolute_path():
    state = workspace_state.add_context_source(workspace_state.empty('w1'),
        {'kind': 'local_repository', 'id': 'local-repo:abc', 'label': 'Cordia', 'path': 'C:/secret/Cordia'})
    assert state['context_sources'][-1] == {'kind': 'local_repository', 'id': 'local-repo:abc', 'label': 'Cordia'}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_workspace_state.TestWorkspaceState.test_adds_local_repository_context_without_absolute_path -v`

Expected: FAIL because only GitHub repository context is accepted.

- [ ] **Step 3: Implement the constrained local context projection**

```python
if source.get('kind') not in {'github_repository', 'local_repository'}: raise ValueError(...)
source = {'kind': kind, 'id': bounded_id, 'label': bounded_label}
```

- [ ] **Step 4: Run focused state and frontend parse tests**

Run: `python -m unittest tests.test_workspace_state -v` and parse `web/interface.html` with `node --check`.

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/surveyor/workspace_state.py backend/tests/test_workspace_state.py web/interface.html desktop/preload.js
git commit -m "feat: add local repository workspace provenance"
```

### Task 5: Package and install the saved-workspace desktop app

**Files:**
- Create: `desktop/install.ps1`
- Modify: `desktop/package.json`
- Modify: `desktop/README.md`
- Modify: `web/interface.html`
- Create: `desktop/test/install.test.ps1`

**Interfaces:**
- The workspace UI exposes “Install Cordia Desktop” only after a saved workspace loads.
- `install.ps1` verifies Windows and a packaged installer path, then starts the installer; it never creates a new workspace.

- [ ] **Step 1: Write failing installer safety tests**

```powershell
It 'refuses to run outside Windows' { ... }
It 'requires a packaged installer rather than downloading arbitrary code' { ... }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `Invoke-Pester desktop/test/install.test.ps1`

Expected: FAIL because installer script does not exist.

- [ ] **Step 3: Implement local packaged-installer invocation**

```powershell
param([string]$InstallerPath = "$PSScriptRoot\dist\Cordia Setup.exe")
if (-not (Test-Path -LiteralPath $InstallerPath)) { throw 'Build the signed Cordia installer before running this script.' }
Start-Process -FilePath $InstallerPath -Wait
```

- [ ] **Step 4: Run installer tests and Electron packaging**

Run: `Invoke-Pester desktop/test/install.test.ps1`; `cd desktop && npm run package`.

Expected: PASS and a Windows installer artifact.

- [ ] **Step 5: Commit**

```bash
git add desktop web/interface.html
git commit -m "feat: package Cordia desktop installer"
```

### Task 6: Write the MVP live setup and test manual

**Files:**
- Create: `docs/LIVE_SETUP_AND_TEST_MANUAL.md`

**Interfaces:**
- Documents localhost database/startup, account creation in dev mode, GitHub token setup, cloud deployment, Electron packaging/installation, and the end-to-end acceptance checklist.

- [ ] **Step 1: Write the manual with secret-safe placeholders**

Include exact commands for `CORDIA_PG_DSN`, generating `CORDIA_VAULT_KEY`, dev-only `CORDIA_DEV_2FA=1`, `CORDIA_COOKIE_SECURE=0`, API health check, GitHub token metadata permission, package build, and rollback.

- [ ] **Step 2: Validate every referenced local command**

Run each non-secret command in a clean shell or label it as production-host-only when it needs VPS authority.

- [ ] **Step 3: Commit**

```bash
git add docs/LIVE_SETUP_AND_TEST_MANUAL.md
git commit -m "docs: add Cordia live setup and test manual"
```
