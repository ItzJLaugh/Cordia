const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const repoRoot = path.resolve(__dirname, '..', '..');
const webRoot = path.join(repoRoot, 'web');
const {
  buildAlidoraNavigation,
  buildWorkspaceNavigation,
} = require('../../web/assets/workspace-navigation.js');

function trackedFiles() {
  return new Set(childProcess.execFileSync(
    'git', ['ls-files', '--cached', '--', 'web/dashboard'],
    { cwd: repoRoot, encoding: 'utf8' },
  ).split(/\r?\n/).filter(Boolean).map((file) => file.replaceAll('\\', '/')));
}

test('the primary Cordia destination and every built index asset are tracked files', () => {
  const navigation = buildWorkspaceNavigation('w-1');
  const destination = new URL(navigation.href, 'https://cordia.example.test/interfaces.html');
  assert.equal(destination.pathname, '/dashboard/');
  assert.equal(destination.search, '?workspace=w-1');

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

test('the committed production bundle contains Workspace primary and Alidora advanced fixed contracts', () => {
  const primary = buildWorkspaceNavigation('w-1');
  const advanced = buildAlidoraNavigation('w-1');
  assert.equal(primary.href, '/dashboard/?workspace=w-1');
  assert.equal(advanced.href, '/dashboard/?workspace=w-1&view=alidora');

  const index = fs.readFileSync(path.join(webRoot, 'dashboard', 'index.html'), 'utf8');
  assert.match(index, /<title>Workspace &mdash; Cordia<\/title>/);
  assert.doesNotMatch(index, /<title>Alidora/);
  const scriptReferences = [...index.matchAll(/<script[^>]+src="([^"]+)"/g)]
    .map((match) => match[1]);
  assert.ok(scriptReferences.length > 0, 'built index must reference a JavaScript bundle');
  const bundle = scriptReferences.map((reference) => fs.readFileSync(
    path.resolve(webRoot, `.${new URL(reference, 'https://cordia.example.test').pathname}`),
    'utf8',
  )).join('\n');

  for (const contract of [
    'Choose a workspace',
    'Workspace',
    'Alidora',
    'Advanced',
    '/surveyor/workspace?id=',
    '/surveyor/alidora/map?id=',
    '/surveyor/run',
    '/surveyor/skill/execute',
  ]) {
    assert.ok(bundle.includes(contract), `built bundle must contain ${contract}`);
  }
});
