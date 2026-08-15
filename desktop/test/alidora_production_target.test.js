const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const repoRoot = path.resolve(__dirname, '..', '..');
const webRoot = path.join(repoRoot, 'web');
const {
  buildAlidoraNavigation,
  buildWorkspaceNavigation,
} = require('../../web/assets/workspace-navigation.js');

function indexBlob(relativePath) {
  return childProcess.execFileSync(
    'git', ['show', `:${relativePath}`],
    { cwd: repoRoot, encoding: null, windowsHide: true },
  );
}

function indexFiles(pathspecs) {
  return childProcess.execFileSync(
    'git', ['ls-files', '--cached', '--', ...pathspecs],
    { cwd: repoRoot, encoding: 'utf8', windowsHide: true },
  ).split(/\r?\n/).filter(Boolean).map((file) => file.replaceAll('\\', '/')).sort();
}

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function canonicalInput(value) {
  return value.toString('utf8').replace(/\r\n?/g, '\n');
}

function sourceInputHash(files) {
  const aggregate = crypto.createHash('sha256');
  for (const file of files) {
    const digest = sha256(Buffer.from(canonicalInput(indexBlob(`dashboard-app/${file}`)), 'utf8'));
    aggregate.update(`${file}\n${digest}\n`, 'utf8');
  }
  return aggregate.digest('hex');
}

test('the primary Cordia destination and every built index asset are tracked files', () => {
  const navigation = buildWorkspaceNavigation('w-1');
  const destination = new URL(navigation.href, 'https://cordia.example.test/interfaces.html');
  assert.equal(destination.pathname, '/dashboard/');
  assert.equal(destination.search, '?workspace=w-1');

  const indexPath = path.join(webRoot, destination.pathname, 'index.html');
  assert.equal(fs.existsSync(indexPath), true, 'web/dashboard/index.html must be built');

  const index = indexBlob('web/dashboard/index.html').toString('utf8');
  assert.equal(sha256(fs.readFileSync(indexPath)), sha256(Buffer.from(index)), 'worktree index must match Git index blob');
  const assetReferences = [...index.matchAll(/(?:src|href)="([^"]+)"/g)]
    .map((match) => match[1])
    .filter((reference) => reference.startsWith('/dashboard/'));
  assert.ok(assetReferences.length > 0, 'built index must reference at least one dashboard asset');

  for (const reference of assetReferences) {
    const pathname = new URL(reference, 'https://cordia.example.test').pathname;
    const assetPath = path.resolve(webRoot, `.${pathname}`);
    assert.equal(assetPath.startsWith(path.resolve(webRoot, 'dashboard') + path.sep), true, reference);
    const relative = path.relative(repoRoot, assetPath).replaceAll('\\', '/');
    const blob = indexBlob(relative);
    assert.equal(fs.existsSync(assetPath), true, `${reference} must resolve under web/dashboard`);
    assert.equal(sha256(fs.readFileSync(assetPath)), sha256(blob), `${relative} worktree must match Git index blob`);
  }
});

test('the committed production bundle contains Workspace primary and Alidora advanced fixed contracts', () => {
  const primary = buildWorkspaceNavigation('w-1');
  const advanced = buildAlidoraNavigation('w-1');
  assert.equal(primary.href, '/dashboard/?workspace=w-1');
  assert.equal(advanced.href, '/dashboard/?workspace=w-1&view=alidora');

  const index = indexBlob('web/dashboard/index.html').toString('utf8');
  assert.match(index, /<title>Workspace &mdash; Cordia<\/title>/);
  assert.doesNotMatch(index, /<title>Alidora/);
  const scriptReferences = [...index.matchAll(/<script[^>]+src="([^"]+)"/g)]
    .map((match) => match[1]);
  assert.ok(scriptReferences.length > 0, 'built index must reference a JavaScript bundle');
  const bundle = scriptReferences.map((reference) => indexBlob(
    `web${new URL(reference, 'https://cordia.example.test').pathname}`,
  ).toString('utf8')).join('\n');

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

test('committed build provenance binds reviewed dashboard inputs to exact output blobs', () => {
  const manifestPath = 'web/dashboard/build-provenance.json';
  const manifestBlob = indexBlob(manifestPath);
  const manifest = JSON.parse(manifestBlob.toString('utf8'));
  const worktreeManifest = fs.readFileSync(path.join(repoRoot, manifestPath));
  assert.equal(sha256(worktreeManifest), sha256(manifestBlob), 'worktree manifest must match Git index blob');
  assert.deepEqual(Object.keys(manifest).sort(), ['algorithm', 'outputs', 'schema', 'source']);
  assert.equal(manifest.schema, 1);
  assert.equal(manifest.algorithm, 'sha256');
  assert.equal(manifest.source.normalization, 'lf');

  const expectedInputs = indexFiles([
    'dashboard-app/package.json',
    'dashboard-app/package-lock.json',
    'dashboard-app/vite.config.js',
    'dashboard-app/src',
  ]).map((file) => file.slice('dashboard-app/'.length));
  assert.deepEqual(manifest.source.files, expectedInputs);
  assert.equal(manifest.source.sha256, sourceInputHash(expectedInputs));

  const index = indexBlob('web/dashboard/index.html').toString('utf8');
  const referencedOutputs = [...index.matchAll(/(?:src|href)="\/dashboard\/([^"]+)"/g)]
    .map((match) => match[1]).sort();
  const declaredOutputs = manifest.outputs.map((output) => output.path).sort();
  assert.deepEqual(declaredOutputs, ['index.html', ...referencedOutputs].sort());

  for (const output of manifest.outputs) {
    assert.match(output.path, /^(?:index\.html|assets\/index-[A-Za-z0-9_-]+\.(?:css|js))$/);
    assert.match(output.sha256, /^[a-f0-9]{64}$/);
    const relative = `web/dashboard/${output.path}`;
    const blob = indexBlob(relative);
    assert.equal(output.sha256, sha256(blob), `${relative} committed blob hash`);
    assert.equal(output.sha256, sha256(fs.readFileSync(path.join(repoRoot, relative))), `${relative} worktree hash`);
  }

  const serialized = JSON.stringify(manifest);
  assert.equal(/[A-Za-z]:\\|\\\\|generatedAt|timestamp|secret|token/i.test(serialized), false);
});
