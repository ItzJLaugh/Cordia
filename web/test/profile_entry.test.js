const assert = require('node:assert/strict');
const test = require('node:test');

require('../assets/workspace-navigation.js');
const { resolveCordiaEntry } = require('../assets/profile-entry.js');

test('a calibrated owner resumes one canonical workspace', async () => {
  const destination = await resolveCordiaEntry({
    getJson: async (path) => path === '/surveyor/profile-calibration'
      ? { ok: true, calibrated: true, workspace_id: 'workspace-1' }
      : null,
    postJson: async () => { throw new Error('must not post'); },
    locationSearch: '',
  });
  assert.equal(destination, '/dashboard/?workspace=workspace-1');
});

test('an uncalibrated owner receives only the configured survey start URL', async () => {
  const destination = await resolveCordiaEntry({
    getJson: async () => ({ ok: true, calibrated: false,
                            survey_url: 'https://cordia-survey1.vercel.app/survey?state=opaque' }),
    postJson: async () => { throw new Error('must not post'); },
    locationSearch: '',
  });
  assert.equal(destination,
               'https://cordia-survey1.vercel.app/survey?state=opaque');
});

test('a callback sends only state and result id to the fixed completion route', async () => {
  const calls = [];
  const destination = await resolveCordiaEntry({
    getJson: async () => { throw new Error('must not get'); },
    postJson: async (...args) => {
      calls.push(args);
      return { ok: true, workspace_id: 'workspace-1' };
    },
    locationSearch: '?state=signed-state&result_id=result_123',
  });
  assert.equal(destination, '/dashboard/?workspace=workspace-1');
  assert.deepEqual(calls, [[
    '/surveyor/profile-calibration/complete',
    { state: 'signed-state', result_id: 'result_123' },
  ]]);
});

test('an incomplete callback or unsafe server destination fails closed', async () => {
  const missingResult = await resolveCordiaEntry({
    getJson: async () => { throw new Error('must not get'); },
    postJson: async () => { throw new Error('must not post'); },
    locationSearch: '?state=signed-state',
  });
  assert.equal(missingResult, '/');

  const unsafeSurvey = await resolveCordiaEntry({
    getJson: async () => ({ ok: true, calibrated: false,
                            survey_url: 'https://attacker.test/survey?state=opaque' }),
    postJson: async () => { throw new Error('must not post'); },
    locationSearch: '',
  });
  assert.equal(unsafeSurvey, '/');
});
