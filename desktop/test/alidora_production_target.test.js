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

function gitBlob(treeish, relativePath) {
  return childProcess.execFileSync(
    'git', ['show', `${treeish}:${relativePath}`],
    { cwd: repoRoot, encoding: null, windowsHide: true },
  );
}

function headBlob(relativePath) {
  return gitBlob('HEAD', relativePath);
}

function indexBlob(relativePath) {
  return gitBlob('', relativePath);
}

function headFiles(pathspecs) {
  return childProcess.execFileSync(
    'git', ['ls-tree', '-r', '--name-only', 'HEAD', '--', ...pathspecs],
    { cwd: repoRoot, encoding: 'utf8', windowsHide: true },
  ).split(/\r?\n/).filter(Boolean).map((file) => file.replaceAll('\\', '/')).sort();
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
    const digest = sha256(Buffer.from(canonicalInput(headBlob(`dashboard-app/${file}`)), 'utf8'));
    aggregate.update(`${file}\n${digest}\n`, 'utf8');
  }
  return aggregate.digest('hex');
}

function assertHeadReleaseBytes(relativePath, { normalizedTextWorktree = false } = {}) {
  const head = headBlob(relativePath);
  assert.equal(indexBlob(relativePath).equals(head), true, `${relativePath} Git index bytes must match HEAD`);
  const worktree = fs.readFileSync(path.join(repoRoot, relativePath));
  const comparableHead = normalizedTextWorktree ? Buffer.from(canonicalInput(head), 'utf8') : head;
  const comparableWorktree = normalizedTextWorktree ? Buffer.from(canonicalInput(worktree), 'utf8') : worktree;
  assert.equal(comparableWorktree.equals(comparableHead), true, `${relativePath} worktree release bytes must match HEAD`);
  return head;
}

test('the primary Cordia destination and every built index asset are tracked files', () => {
  const navigation = buildWorkspaceNavigation('w-1');
  const destination = new URL(navigation.href, 'https://cordia.example.test/interfaces.html');
  assert.equal(destination.pathname, '/dashboard/');
  assert.equal(destination.search, '?workspace=w-1');

  const indexPath = path.join(webRoot, destination.pathname, 'index.html');
  assert.equal(fs.existsSync(indexPath), true, 'web/dashboard/index.html must be built');

  const index = assertHeadReleaseBytes('web/dashboard/index.html').toString('utf8');
  const assetReferences = [...index.matchAll(/(?:src|href)="([^"]+)"/g)]
    .map((match) => match[1])
    .filter((reference) => reference.startsWith('/dashboard/'));
  assert.ok(assetReferences.length > 0, 'built index must reference at least one dashboard asset');

  for (const reference of assetReferences) {
    const pathname = new URL(reference, 'https://cordia.example.test').pathname;
    const assetPath = path.resolve(webRoot, `.${pathname}`);
    assert.equal(assetPath.startsWith(path.resolve(webRoot, 'dashboard') + path.sep), true, reference);
    const relative = path.relative(repoRoot, assetPath).replaceAll('\\', '/');
    assertHeadReleaseBytes(relative);
    assert.equal(fs.existsSync(assetPath), true, `${reference} must resolve under web/dashboard`);
  }
});

test('the committed production bundle contains Workspace primary and Alidora advanced fixed contracts', () => {
  const primary = buildWorkspaceNavigation('w-1');
  const advanced = buildAlidoraNavigation('w-1');
  assert.equal(primary.href, '/dashboard/?workspace=w-1');
  assert.equal(advanced.href, '/dashboard/?workspace=w-1&view=alidora');

  const index = assertHeadReleaseBytes('web/dashboard/index.html').toString('utf8');
  assert.match(index, /<title>Workspace &mdash; Cordia<\/title>/);
  assert.doesNotMatch(index, /<title>Alidora/);
  const scriptReferences = [...index.matchAll(/<script[^>]+src="([^"]+)"/g)]
    .map((match) => match[1]);
  assert.ok(scriptReferences.length > 0, 'built index must reference a JavaScript bundle');
  const bundle = scriptReferences.map((reference) => assertHeadReleaseBytes(
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
  const manifestBlob = assertHeadReleaseBytes(manifestPath);
  const manifest = JSON.parse(manifestBlob.toString('utf8'));
  assert.deepEqual(Object.keys(manifest).sort(), ['algorithm', 'outputs', 'schema', 'source']);
  assert.equal(manifest.schema, 1);
  assert.equal(manifest.algorithm, 'sha256');
  assert.equal(manifest.source.normalization, 'lf');

  const inputPathspecs = [
    'dashboard-app/package.json',
    'dashboard-app/package-lock.json',
    'dashboard-app/vite.config.js',
    'dashboard-app/src',
  ];
  const headInputs = headFiles(inputPathspecs);
  assert.deepEqual(indexFiles(inputPathspecs), headInputs, 'dashboard input file set in Git index must match HEAD');
  for (const input of headInputs) assertHeadReleaseBytes(input, { normalizedTextWorktree: true });
  const expectedInputs = headInputs.map((file) => file.slice('dashboard-app/'.length));
  assert.deepEqual(manifest.source.files, expectedInputs);
  assert.equal(manifest.source.sha256, sourceInputHash(expectedInputs));

  const index = assertHeadReleaseBytes('web/dashboard/index.html').toString('utf8');
  const referencedOutputs = [...index.matchAll(/(?:src|href)="\/dashboard\/([^"]+)"/g)]
    .map((match) => match[1]).sort();
  const declaredOutputs = manifest.outputs.map((output) => output.path).sort();
  assert.deepEqual(declaredOutputs, ['index.html', ...referencedOutputs].sort());

  for (const output of manifest.outputs) {
    assert.match(output.path, /^(?:index\.html|assets\/index-[A-Za-z0-9_-]+\.(?:css|js))$/);
    assert.match(output.sha256, /^[a-f0-9]{64}$/);
    const relative = `web/dashboard/${output.path}`;
    const blob = assertHeadReleaseBytes(relative);
    assert.equal(output.sha256, sha256(blob), `${relative} committed blob hash`);
  }

  const serialized = JSON.stringify(manifest);
  assert.equal(/[A-Za-z]:\\|\\\\|generatedAt|timestamp|secret|token/i.test(serialized), false);
});

test('the explicit clean rebuild verifier is committed and release-identical', () => {
  assertHeadReleaseBytes('desktop/scripts/verify-dashboard-release.js', { normalizedTextWorktree: true });
  const packageBlob = assertHeadReleaseBytes('desktop/package.json', { normalizedTextWorktree: true });
  const packageJson = JSON.parse(packageBlob.toString('utf8'));
  assert.equal(packageJson.scripts['verify:dashboard-release'], 'node scripts/verify-dashboard-release.js');
});
