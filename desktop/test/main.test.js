const assert = require('node:assert/strict');
const test = require('node:test');

const { buildWindowOptions, cloudUrl } = require('../window_config');

test('creates an isolated BrowserWindow configuration', () => {
  const options = buildWindowOptions();

  assert.equal(options.webPreferences.contextIsolation, true);
  assert.equal(options.webPreferences.nodeIntegration, false);
  assert.equal(options.webPreferences.sandbox, true);
});

test('uses the Cordia cloud origin by default', () => {
  assert.equal(cloudUrl({}), 'https://cordiacode.com');
});

test('only accepts localhost as an explicit development preview', () => {
  assert.equal(cloudUrl({ CORDIA_DESKTOP_URL: 'http://localhost:9995' }), 'http://localhost:9995');
  assert.throws(
    () => cloudUrl({ CORDIA_DESKTOP_URL: 'https://untrusted.example' }),
    /CORDIA_DESKTOP_URL must be https:\/\/cordiacode\.com or a localhost URL/,
  );
});
