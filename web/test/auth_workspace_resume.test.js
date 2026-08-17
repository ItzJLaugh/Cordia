const assert = require('node:assert/strict');
const test = require('node:test');

// Load the browser-shared dependency before the coordinator, just as the
// sign-in page does.
require('../assets/workspace-navigation.js');
const { resumeAuthenticatedWorkspace } = require('../assets/cordia-auth-flow.js');

function successfulInterfaces(interfaces) {
  return {
    ok: true,
    json: async () => ({ interfaces }),
  };
}

async function resume(response) {
  const calls = [];
  const destinations = [];
  const destination = await resumeAuthenticatedWorkspace({
    apiBase: 'https://cordia.example.test:9995',
    fetch: async (...args) => {
      calls.push(args);
      return response;
    },
    navigate: (value) => destinations.push(value),
  });
  return { calls, destination, destinations };
}

test('resumes the authoritative first safe saved workspace through the primary dashboard', async () => {
  const result = await resume(successfulInterfaces([
    { id: 'workspace-1_A.2' },
    { id: 'later-safe-workspace' },
  ]));

  assert.equal(result.destination, '/dashboard/?workspace=workspace-1_A.2');
  assert.deepEqual(result.destinations, ['/dashboard/?workspace=workspace-1_A.2']);
  assert.deepEqual(result.calls, [[
    'https://cordia.example.test:9995/surveyor/interfaces',
    { method: 'GET', credentials: 'same-origin' },
  ]]);
  assert.equal(result.destination.includes('view=alidora'), false);
});

test('fails closed to Surveyor when no saved workspace is available', async () => {
  const result = await resume(successfulInterfaces([]));

  assert.equal(result.destination, 'surveyor.html');
  assert.deepEqual(result.destinations, ['surveyor.html']);
});

test('fails closed when the interface response is failed or malformed', async () => {
  const scenarios = [
    { ok: false, json: async () => ({ interfaces: [{ id: 'safe' }] }) },
    { ok: true, json: async () => ({}) },
    { ok: true, json: async () => { throw new Error('transport details must stay private'); } },
  ];

  for (const response of scenarios) {
    const result = await resume(response);
    assert.equal(result.destination, 'surveyor.html');
    assert.deepEqual(result.destinations, ['surveyor.html']);
  }
});

test('fails closed without exposing a rejected interface-read error', async () => {
  const calls = [];
  const destinations = [];
  const destination = await resumeAuthenticatedWorkspace({
    apiBase: 'https://cordia.example.test:9995',
    fetch: async (...args) => {
      calls.push(args);
      throw new Error('transport details must stay private');
    },
    navigate: (value) => destinations.push(value),
  });

  assert.equal(destination, 'surveyor.html');
  assert.deepEqual(destinations, ['surveyor.html']);
  assert.deepEqual(calls, [[
    'https://cordia.example.test:9995/surveyor/interfaces',
    { method: 'GET', credentials: 'same-origin' },
  ]]);
  assert.doesNotMatch(destination, /transport details|private/i);
});

test('does not scan past an unsafe first saved workspace id', async () => {
  for (const unsafeId of [
    '/private/workspace',
    'C:\\private\\workspace',
    'github_pat_abcdefghijklmnopqrstuvwxyz0123456789',
  ]) {
    const result = await resume(successfulInterfaces([
      { id: unsafeId },
      { id: 'later-safe-workspace' },
    ]));

    assert.equal(result.destination, 'surveyor.html', unsafeId);
    assert.deepEqual(result.destinations, ['surveyor.html'], unsafeId);
  }
});
