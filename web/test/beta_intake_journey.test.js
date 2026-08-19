const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function browserModules() {
  const context = vm.createContext({
    URL,
    URLSearchParams,
    console,
    globalThis: null,
    self: null,
  });
  context.globalThis = context;
  context.self = context;
  for (const file of [
    'workspace-navigation.js',
    'operator-profile.js',
    'cordia-workspace-generation.js',
    'cordia-auth-flow.js',
  ]) {
    vm.runInContext(
      fs.readFileSync(path.join(__dirname, '..', 'assets', file), 'utf8'),
      context,
      { filename: file },
    );
  }
  return context;
}

test('operator assessment generates then resumes the exact same canonical workspace', async () => {
  const browser = browserModules();
  const model = browser.CordiaOperatorProfile.buildOperatorProfileModel({
    ok: true,
    operator_profile: {
      title: 'What Cordia currently understands',
      identifiers: [],
      understanding: [],
      evidence: [],
      connectors: [],
      still_learning: [],
      next_action: {
        type: 'create_interface',
        label: 'Build my workspace',
        reason: 'Surveyor intake is complete.',
      },
      latest_workspace: null,
    },
  }, browser.CordiaWorkspaceNavigation);
  assert.equal(model.primaryAction.kind, 'generate');

  const generated = await browser.CordiaWorkspaceGeneration.generate({
    fetch: async () => ({
      ok: true,
      json: async () => ({ ok: true, id: 'workspace-1', created: true }),
    }),
    navigation: browser.CordiaWorkspaceNavigation,
  });
  assert.equal(generated.href, '/dashboard/?workspace=workspace-1');

  const destinations = [];
  const resumed = await browser.CordiaAuthFlow.resumeAuthenticatedWorkspace({
    apiBase: '',
    fetch: async () => ({
      ok: true,
      json: async () => ({ interfaces: [{ id: 'workspace-1' }] }),
    }),
    navigate: (destination) => destinations.push(destination),
  });
  assert.equal(resumed, generated.href);
  assert.deepEqual(destinations, ['/dashboard/?workspace=workspace-1']);
});

test('resume never scans past an unsafe or malformed first interface', async () => {
  const browser = browserModules();
  for (const first of [
    { id: '/private/workspace' },
    { id: 'github_pat_abcdefghijklmnopqrstuvwxyz0123456789' },
    null,
  ]) {
    const destinations = [];
    const resumed = await browser.CordiaAuthFlow.resumeAuthenticatedWorkspace({
      apiBase: '',
      fetch: async () => ({
        ok: true,
        json: async () => ({ interfaces: [first, { id: 'later-safe-workspace' }] }),
      }),
      navigate: (destination) => destinations.push(destination),
    });
    assert.equal(resumed, 'surveyor.html');
    assert.deepEqual(destinations, ['surveyor.html']);
  }
});

test('Surveyor primary path does not route users into builder or certification surfaces', () => {
  for (const file of [
    'assets/cordia-surveyor.js',
    'assets/operator-profile.js',
    'surveyor.html',
    'profile.html',
  ]) {
    const source = fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
    assert.doesNotMatch(source, /(?:assessment|certifications|builder)\.html/i, file);
  }
});
