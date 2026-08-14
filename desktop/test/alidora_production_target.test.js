const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const repoRoot = path.resolve(__dirname, '..', '..');
const webRoot = path.join(repoRoot, 'web');
const { buildAlidoraNavigation } = require('../../web/assets/workspace-navigation.js');

function trackedFiles() {
  return new Set(childProcess.execFileSync(
    'git', ['ls-files', '--cached', '--', 'web/dashboard'],
    { cwd: repoRoot, encoding: 'utf8' },
  ).split(/\r?\n/).filter(Boolean).map((file) => file.replaceAll('\\', '/')));
}

test('the Cordia Alidora destination and every built index asset are tracked files', () => {
  const navigation = buildAlidoraNavigation('w-1');
  const destination = new URL(navigation.href, 'https://cordia.example.test/interface.html');
  assert.equal(destination.pathname, '/dashboard/');

  const indexPath = path.join(webRoot, destination.pathname, 'index.html');
  assert.equal(fs.existsSync(indexPath), true, 'web/dashboard/index.html must be built');

  const tracked = trackedFiles();
  assert.equal(tracked.has('web/dashboard/index.html'), true, 'dashboard index must be staged or committed');

  const index = fs.readFileSync(indexPath, 'utf8');
  const assetReferences = [...index.matchAll(/(?:src|href)="([^"]+)"/g)]
    .map((match) => match[1])
    .filter((reference) => reference.startsWith('/dashboard/'));
  assert.ok(assetReferences.length > 0, 'built index must reference at least one dashboard asset');

  for (const reference of assetReferences) {
    const pathname = new URL(reference, 'https://cordia.example.test').pathname;
    const assetPath = path.resolve(webRoot, `.${pathname}`);
    assert.equal(assetPath.startsWith(path.resolve(webRoot, 'dashboard') + path.sep), true, reference);
    assert.equal(fs.existsSync(assetPath), true, `${reference} must resolve under web/dashboard`);
    const relative = path.relative(repoRoot, assetPath).replaceAll('\\', '/');
    assert.equal(tracked.has(relative), true, `${relative} must be staged or committed`);
  }
});
