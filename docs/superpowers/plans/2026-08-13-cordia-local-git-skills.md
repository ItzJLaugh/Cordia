# Cordia Local Git Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add secure, testable local Git status/wait, pull, and push skills to Cordia Desktop.

**Architecture:** Electron main keeps opaque repository-ID to local-path mappings private. A fixed-argument, no-shell adapter runs Git. The preload offers named methods only. Status/wait are read-only; pull/push are locally approved once, expire, and revalidate immediately before execution.

**Tech Stack:** Electron, Node built-ins, Node native test runner, existing Cordia Python manifests.

**Spec:** `docs/superpowers/specs/2026-08-13-cordia-local-git-skills-design.md`

## Global Constraints

- Never expose arbitrary IPC, terminal access, paths, source content, remote URLs, credentials, Git arguments, refspecs, or environment.
- Only user-selected repositories may be used; paths remain Electron-main local.
- Use fixed Git argv and `shell: false`; status/wait never mutate.
- Pull is `git pull --ff-only`; push is configured-upstream `git push` only.
- Pull/push need matching, approved, unexpired, single-use local approval and reject dirty/no-upstream/changed-branch state first.
- Bound subprocess output to 8192 bytes; preserve Electron security settings; use TDD.

---

### Task 1: Add fixed Git status adapter

**Files:** Create `desktop/git_adapter.js`, `desktop/test/git_adapter.test.js`.

**Interfaces:** `fixedArgs(operation)` accepts only `status`, `pull`, `push` or throws `Unsupported Git operation.`. `status(repositoryPath, execFile)` returns `{branch, clean, ahead, behind, upstream}`. `run` invokes `execFile('git', fixedArgs(operation), {cwd: repositoryPath, shell: false, maxBuffer: 8192}, callback)`.

- [ ] **Step 1: Write failing tests**

```js
test('uses fixed no-shell argv', async () => {
  await status('C:/private/repository', (bin, args, options, done) => {
    assert.deepEqual([bin, args, options], ['git', ['status', '--porcelain=v1', '--branch'], { cwd: 'C:/private/repository', shell: false, maxBuffer: 8192 }]);
    done(null, '## main...origin/main [ahead 2, behind 1]\n M README.md\n', '');
  });
});
test('rejects arbitrary operation', () => assert.throws(() => fixedArgs('reset --hard'), /Unsupported Git operation/));
```

- [ ] **Step 2: Verify RED**

Run: `cd desktop && npm.cmd test -- test/git_adapter.test.js`.

Expected: FAIL because the adapter does not exist.

- [ ] **Step 3: Implement minimally**

```js
const FIXED_ARGS = Object.freeze({ status: ['status', '--porcelain=v1', '--branch'], pull: ['pull', '--ff-only'], push: ['push'] });
function fixedArgs(operation) { if (!FIXED_ARGS[operation]) throw new Error('Unsupported Git operation.'); return [...FIXED_ARGS[operation]]; }
```

- [ ] **Step 4: Verify GREEN**

Run: `cd desktop && npm.cmd test -- test/git_adapter.test.js`.

Expected: PASS for clean/dirty, ahead/behind, detached/no-upstream, and unknown operation cases.

- [ ] **Step 5: Commit**

```bash
git add desktop/git_adapter.js desktop/test/git_adapter.test.js
git commit -m "feat: add fixed local Git status adapter"
```

### Task 2: Add selected-repository registry plus status/wait

**Files:** Create `desktop/repository_registry.js`, `desktop/git_skills.js`, `desktop/test/git_skills.test.js`; modify `desktop/main.js`, `desktop/preload_api.js`, `desktop/test/preload_api.test.js`.

**Interfaces:** `RepositoryRegistry.register(metadata, selectedPath)` retains selectedPath only in main; `resolve(id)` returns it only to main callers or throws `Selected repository is unavailable.`. `GitSkills.status(id)` returns safe status. `GitSkills.wait(id, condition, options)` accepts only `clean`, `incoming_changes`, `synchronized`, bounded 250-2000ms interval and 1-60s timeout. Preload adds `gitStatus(id)` and `gitWait(id, condition)` only.

- [ ] **Step 1: Write failing service and bridge tests**

```js
test('keeps paths out of status output', async () => {
  registry.register({ id: 'local-repo:a', label: 'Cordia' }, 'C:/private/Cordia');
  assert.equal(Object.hasOwn(await skills.status('local-repo:a'), 'path'), false);
});
test('wait times out without mutation', async () => {
  assert.equal((await skills.wait('local-repo:a', 'synchronized', { timeoutMs: 1 })).timed_out, true);
  assert.deepEqual(adapter.operations, ['status']);
});
```

- [ ] **Step 2: Verify RED**

Run: `cd desktop && npm.cmd test -- test/git_skills.test.js test/preload_api.test.js`.

Expected: FAIL because registry/service methods and IPC channels do not exist.

- [ ] **Step 3: Implement bounded registry/polling**

```js
const CONDITIONS = new Set(['clean', 'incoming_changes', 'synchronized']);
function matches(status, condition) { return (condition === 'clean' && status.clean) || (condition === 'incoming_changes' && status.behind > 0) || (condition === 'synchronized' && status.clean && status.ahead === 0 && status.behind === 0); }
ipcMain.handle('cordia-desktop:git-status', (_event, id) => skills.status(id));
ipcMain.handle('cordia-desktop:git-wait', (_event, id, condition) => skills.wait(id, condition));
```

- [ ] **Step 4: Verify GREEN**

Run: `cd desktop && npm.cmd test -- test/git_skills.test.js test/preload_api.test.js`.

Expected: PASS for missing selection, safe shape, each condition, timeout, no generic IPC.

- [ ] **Step 5: Commit**

```bash
git add desktop/repository_registry.js desktop/git_skills.js desktop/main.js desktop/preload_api.js desktop/test
git commit -m "feat: add read-only local Git status and wait skills"
```

### Task 3: Add local one-use approval plus pull/push

**Files:** Create `desktop/local_approvals.js`, `desktop/test/local_approvals.test.js`; modify `desktop/git_skills.js`, `desktop/main.js`, `desktop/preload_api.js`, associated tests.

**Interfaces:** `LocalApprovals.create(descriptor)`, `decide(id, approved)`, `consume(id, descriptor, now)` create opaque five-minute one-use approvals; invalid use throws `Local Git approval is not valid.`. `GitSkills.preview(id, operation)` accepts only `pull`/`push`; `execute(approvalId)` rechecks status/branch/upstream. Preload adds `gitPreview(id, operation)` and `gitExecute(approvalId)` only; Electron native confirmation completes approval.

- [ ] **Step 1: Write failing approval/mutation tests**

```js
test('cannot consume pending, expired, declined, or reused approval', () => {
  const record = approvals.create(descriptor);
  assert.throws(() => approvals.consume(record.id, descriptor, now), /not valid/);
  approvals.decide(record.id, true); approvals.consume(record.id, descriptor, now);
  assert.throws(() => approvals.consume(record.id, descriptor, now), /not valid/);
});
test('dirty status blocks before mutation', async () => {
  await assert.rejects(() => skills.execute(approvedId), /working tree must be clean/);
  assert.deepEqual(adapter.operations, ['status']);
});
```

- [ ] **Step 2: Verify RED**

Run: `cd desktop && npm.cmd test -- test/local_approvals.test.js test/git_skills.test.js`.

Expected: FAIL because approvals, preview, and execute do not exist.

- [ ] **Step 3: Implement local approval and revalidation**

```js
async function execute(approvalId) {
  const descriptor = this.approvals.descriptorFor(approvalId); const before = await this.status(descriptor.repository_id);
  if (!before.clean) throw new Error('The working tree must be clean before Git pull or push.');
  if (!before.upstream || before.branch !== descriptor.branch) throw new Error('Repository state changed; create a new preview.');
  this.approvals.consume(approvalId, descriptor, this.now());
  await this.adapter.run(this.registry.resolve(descriptor.repository_id), descriptor.operation);
  return { operation: descriptor.operation, branch: descriptor.branch, completed: true };
}
```

- [ ] **Step 4: Verify GREEN**

Run: `cd desktop && npm.cmd test -- test/local_approvals.test.js test/git_skills.test.js test/preload_api.test.js`.

Expected: PASS for expiry/decline/reuse/mismatch, dirty/no-upstream/branch-change, fixed argv, no arbitrary mutation API.

- [ ] **Step 5: Commit**

```bash
git add desktop/local_approvals.js desktop/git_skills.js desktop/main.js desktop/preload_api.js desktop/test
git commit -m "feat: add approval-gated local Git pull and push skills"
```

### Task 4: Surface capability truth and disposable-repository proof

**Files:** Modify `backend/surveyor/capability_gateway.py`, `backend/surveyor/permissions.py`, `backend/surveyor/skills.py`, their tests, and `desktop/README.md`; create `desktop/test/disposable_repository.test.js`.

**Interfaces:** Catalog declares `desktop.git.status`, `.wait`, `.pull`, `.push` with `local_bridge`. Status/wait are ALLOW only with `desktop.local_repository: confirmed`; pull/push are ASK. Manifests declare `local_git_status_wait`, `local_git_pull`, `local_git_push`.

- [ ] **Step 1: Write failing contract and integration tests**

```python
def test_requires_local_selection_for_status():
    assert permissions.decide('desktop.git.status', {})['decision'] == 'ASK'
    assert permissions.decide('desktop.git.status', {'desktop.local_repository': 'confirmed'})['decision'] == 'ALLOW'
def test_keeps_push_approval_gated():
    assert permissions.decide('desktop.git.push', {'desktop.local_repository': 'confirmed'})['decision'] == 'ASK'
```

```js
test('declined pull never invokes mutation', async () => {
  const preview = await skills.preview(repositoryId, 'pull'); approvals.decide(preview.approval.id, false);
  await assert.rejects(() => skills.execute(preview.approval.id), /not valid/);
});
```

- [ ] **Step 2: Verify RED**

Run: `cd backend && python -m unittest tests.test_capability_gateway tests.test_skills -v`; `cd desktop && npm.cmd test -- test/disposable_repository.test.js`.

Expected: FAIL because catalog entries, local-state rules, manifests, and integration support do not exist.

- [ ] **Step 3: Implement catalog truth and test manual guidance**

```python
_CAPABILITIES['desktop.git.status'] = {'connector': 'desktop.local_repository', 'permission': 'ALLOW', 'transport': 'local_bridge', 'summary': 'Read a user-selected local Git repository status.'}
_CAPABILITIES['desktop.git.push'] = {'connector': 'desktop.local_repository', 'permission': 'ASK', 'transport': 'local_bridge', 'summary': 'Push the selected branch after fresh local approval.'}
```

- [ ] **Step 4: Verify full slice**

Run: `cd desktop && npm.cmd test`; `cd backend && python -m unittest discover -s tests -v`; `node --check desktop/main.js`; `node --check desktop/git_adapter.js`; `git diff --check`.

Expected: all tests and syntax checks pass; no whitespace errors.

- [ ] **Step 5: Commit**

```bash
git add desktop backend/surveyor backend/tests
git commit -m "feat: surface safe local Git skills in Cordia"
```
