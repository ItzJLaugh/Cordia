const assert = require('node:assert/strict');
const test = require('node:test');

const { RepositoryRegistry } = require('../repository_registry');
const { GitSkills } = require('../git_skills');
const { LocalApprovals } = require('../local_approvals');

function makeSkills(statuses = []) {
  const registry = new RepositoryRegistry();
  registry.register({ id: 'local-repo:a', label: 'Cordia' }, 'C:/private/Cordia');
  const adapter = {
    operations: [],
    async status(repositoryPath) {
      this.operations.push({ operation: 'status', repositoryPath });
      return statuses.shift() || { branch: 'main', clean: true, ahead: 0, behind: 0, upstream: 'origin/main' };
    },
  };
  const sleeps = [];
  const skills = new GitSkills({ registry, adapter, sleep: async (ms) => sleeps.push(ms) });
  return { registry, adapter, sleeps, skills };
}

test('preview rejects non-string and arbitrary operations before creating approval', async () => {
  const { skills } = makeSkills();

  await assert.rejects(() => skills.preview('local-repo:a', ['push']), { message: 'Unsupported Git operation.' });
  await assert.rejects(() => skills.preview('local-repo:a', 'status'), { message: 'Unsupported Git operation.' });
});

test('preview rejects missing selection, dirty tree, detached branch, and no upstream before approval', async () => {
  const cases = [
    ['missing selection', 'local-repo:missing', { branch: 'main', clean: true, ahead: 0, behind: 0, upstream: 'origin/main' }, 'Selected repository is unavailable.'],
    ['dirty tree', 'local-repo:a', { branch: 'main', clean: false, ahead: 0, behind: 0, upstream: 'origin/main' }, 'Git working tree must be clean.'],
    ['detached branch', 'local-repo:a', { branch: null, clean: true, ahead: 0, behind: 0, upstream: 'origin/main' }, 'Git branch must have an upstream.'],
    ['no upstream', 'local-repo:a', { branch: 'main', clean: true, ahead: 0, behind: 0, upstream: null }, 'Git branch must have an upstream.'],
  ];

  for (const [_name, repositoryId, status, message] of cases) {
    const { skills } = makeSkills([status]);
    skills.approvals = new LocalApprovals({ now: () => 1_000 });
    await assert.rejects(() => skills.preview(repositoryId, 'push'), { message });
  }
});

test('executes only fixed approved operation after exact status recheck', async () => {
  const { registry, adapter } = makeSkills([
    { branch: 'main', clean: true, ahead: 0, behind: 0, upstream: 'origin/main' },
    { branch: 'main', clean: true, ahead: 0, behind: 0, upstream: 'origin/main' },
  ]);
  let clock = 1_000;
  const approvals = new LocalApprovals({ now: () => clock });
  const skills = new GitSkills({ registry, adapter, approvals, now: () => clock });
  adapter.run = async (repositoryPath, operation) => adapter.operations.push({ operation, repositoryPath });

  const preview = await skills.preview('local-repo:a', 'pull');
  approvals.decide(preview.approval.id, true);
  const result = await skills.execute(preview.approval.id);

  assert.deepEqual(result, { operation: 'pull', branch: 'main', completed: true });
  assert.deepEqual(adapter.operations, [
    { operation: 'status', repositoryPath: 'C:/private/Cordia' },
    { operation: 'status', repositoryPath: 'C:/private/Cordia' },
    { operation: 'pull', repositoryPath: 'C:/private/Cordia' },
  ]);
  await assert.rejects(() => skills.execute(preview.approval.id), { message: 'Local Git approval is not valid.' });
});

test('does not mutate when branch changes or tree becomes dirty after preview', async () => {
  const cases = [
    { branch: 'other', clean: true, ahead: 0, behind: 0, upstream: 'origin/other' },
    { branch: 'main', clean: false, ahead: 0, behind: 0, upstream: 'origin/main' },
  ];
  for (const recheckedStatus of cases) {
    const { registry, adapter } = makeSkills([
      { branch: 'main', clean: true, ahead: 0, behind: 0, upstream: 'origin/main' },
      recheckedStatus,
    ]);
    const approvals = new LocalApprovals({ now: () => 1_000 });
    const skills = new GitSkills({ registry, adapter, approvals, now: () => 1_000 });
    adapter.run = async () => assert.fail('mutation must not run');

    const preview = await skills.preview('local-repo:a', 'push');
    approvals.decide(preview.approval.id, true);
    await assert.rejects(() => skills.execute(preview.approval.id), { message: 'Local Git approval is not valid.' });
  }
});

test('does not mutate when upstream changes with the same branch after preview', async () => {
  const { registry, adapter } = makeSkills([
    { branch: 'main', clean: true, ahead: 0, behind: 0, upstream: 'origin/main' },
    { branch: 'main', clean: true, ahead: 0, behind: 0, upstream: 'backup/main' },
  ]);
  const approvals = new LocalApprovals({ now: () => 1_000 });
  const skills = new GitSkills({ registry, adapter, approvals, now: () => 1_000 });
  adapter.run = async () => assert.fail('mutation must not run');

  const preview = await skills.preview('local-repo:a', 'push');
  approvals.decide(preview.approval.id, true);

  await assert.rejects(() => skills.execute(preview.approval.id), { message: 'Local Git approval is not valid.' });
});

test('returns a safe preview without repository path or approval descriptor', async () => {
  const { registry, adapter } = makeSkills([{ branch: 'main', clean: true, ahead: 0, behind: 0, upstream: 'origin/main' }]);
  const skills = new GitSkills({ registry, adapter, approvals: new LocalApprovals({ now: () => 1_000 }) });

  const preview = await skills.preview('local-repo:a', 'push');

  assert.deepEqual(Object.keys(preview).sort(), ['approval', 'branch', 'operation']);
  assert.equal(JSON.stringify(preview).includes('C:/private/Cordia'), false);
  assert.equal(JSON.stringify(preview).includes('repositoryId'), false);
  assert.equal(JSON.stringify(preview).includes('origin/main'), false);
});

test('keeps selected paths in the main registry and rejects missing selections', async () => {
  const { registry, skills } = makeSkills();

  assert.equal(registry.resolve('local-repo:a'), 'C:/private/Cordia');
  assert.throws(() => registry.resolve('local-repo:missing'), { message: 'Selected repository is unavailable.' });
  await assert.rejects(() => skills.status('local-repo:missing'), { message: 'Selected repository is unavailable.' });
});

test('register returns only safe metadata', () => {
  const registry = new RepositoryRegistry();

  assert.deepEqual(
    registry.register({ id: 'local-repo:a', label: 'Cordia', path: 'C:/private/Cordia' }, 'C:/private/Cordia'),
    { id: 'local-repo:a', label: 'Cordia' },
  );
});

test('keeps paths and upstreams out of public status output', async () => {
  const { skills } = makeSkills([{ branch: 'main', clean: true, ahead: 0, behind: 0, upstream: 'origin/main', path: 'C:/private/Cordia' }]);

  assert.deepEqual(await skills.status('local-repo:a'), {
    branch: 'main', clean: true, ahead: 0, behind: 0,
  });
});

test('wait completes for each supported repository condition', async () => {
  const cases = [
    ['clean', { branch: 'main', clean: true, ahead: 4, behind: 2, upstream: 'origin/main' }],
    ['incoming_changes', { branch: 'main', clean: false, ahead: 0, behind: 1, upstream: 'origin/main' }],
    ['synchronized', { branch: 'main', clean: true, ahead: 0, behind: 0, upstream: 'origin/main' }],
  ];

  for (const [condition, status] of cases) {
    const { skills, sleeps } = makeSkills([status]);
    const result = await skills.wait('local-repo:a', condition, { intervalMs: 250, timeoutMs: 1000 });
    assert.deepEqual(result, {
      condition,
      matched: true,
      timed_out: false,
      status: { branch: status.branch, clean: status.clean, ahead: status.ahead, behind: status.behind },
    });
    assert.deepEqual(sleeps, []);
  }
});

test('wait rejects invalid conditions and out-of-range bounds', async () => {
  const { skills } = makeSkills();

  await assert.rejects(() => skills.wait('local-repo:a', 'push', { timeoutMs: 1000 }), { message: 'Unsupported Git wait condition.' });
  await assert.rejects(() => skills.wait('local-repo:a', 'clean', { intervalMs: 249, timeoutMs: 1000 }), { message: 'Git wait interval must be between 250 and 2000 milliseconds.' });
  await assert.rejects(() => skills.wait('local-repo:a', 'clean', { intervalMs: 2001, timeoutMs: 1000 }), { message: 'Git wait interval must be between 250 and 2000 milliseconds.' });
  await assert.rejects(() => skills.wait('local-repo:a', 'clean', { timeoutMs: 999 }), { message: 'Git wait timeout must be between 1 and 60 seconds.' });
  await assert.rejects(() => skills.wait('local-repo:a', 'clean', { timeoutMs: 60001 }), { message: 'Git wait timeout must be between 1 and 60 seconds.' });
});

test('wait times out through status calls only', async () => {
  const status = { branch: 'main', clean: false, ahead: 1, behind: 0, upstream: 'origin/main' };
  const { adapter, sleeps, skills } = makeSkills([status]);
  let clockMs = 0;
  skills.now = () => clockMs;
  skills.sleep = async (ms) => {
    sleeps.push(ms);
    clockMs += ms;
  };

  const result = await skills.wait('local-repo:a', 'synchronized', { intervalMs: 1000, timeoutMs: 1000 });

  assert.deepEqual(result, {
    condition: 'synchronized', matched: false, timed_out: true,
    status: { branch: status.branch, clean: status.clean, ahead: status.ahead, behind: status.behind },
  });
  assert.deepEqual(adapter.operations, [
    { operation: 'status', repositoryPath: 'C:/private/Cordia' },
  ]);
  assert.deepEqual(sleeps, [1000]);
});

test('wait honors the deadline during status work and never polls after it', async () => {
  let clockMs = 0;
  let statusCalls = 0;
  const sleeps = [];
  const registry = new RepositoryRegistry();
  registry.register({ id: 'local-repo:a', label: 'Cordia' }, 'C:/private/Cordia');
  const status = { branch: 'main', clean: false, ahead: 1, behind: 0, upstream: 'origin/main' };
  const skills = new GitSkills({
    registry,
    adapter: {
      async status() {
        statusCalls += 1;
        clockMs += 250;
        return status;
      },
    },
    now: () => clockMs,
    sleep: async (ms) => {
      sleeps.push(ms);
      clockMs += ms;
    },
  });

  const result = await skills.wait('local-repo:a', 'synchronized', { intervalMs: 2000, timeoutMs: 1000 });

  assert.deepEqual(result, {
    condition: 'synchronized', matched: false, timed_out: true,
    status: { branch: status.branch, clean: status.clean, ahead: status.ahead, behind: status.behind },
  });
  assert.equal(statusCalls, 1);
  assert.deepEqual(sleeps, [750]);
});
