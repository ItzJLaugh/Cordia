const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..', '..');
const temporaryPrefix = 'cordia-dashboard-release-';
const inputPathspecs = [
  'dashboard-app/package.json',
  'dashboard-app/package-lock.json',
  'dashboard-app/vite.config.js',
  'dashboard-app/src',
];

function git(args, encoding = null) {
  return childProcess.execFileSync('git', ['-c', `safe.directory=${repoRoot}`, ...args], {
    cwd: repoRoot,
    encoding,
    windowsHide: true,
  });
}

function headBlob(relativePath) {
  return git(['show', `HEAD:${relativePath}`]);
}

function headInputs() {
  return git(['ls-tree', '-r', '--name-only', 'HEAD', '--', ...inputPathspecs], 'utf8')
    .split(/\r?\n/)
    .filter(Boolean)
    .map((file) => file.replaceAll('\\', '/'))
    .sort();
}

function filesBelow(directory, base = directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) return filesBelow(absolute, base);
    return entry.isFile() ? [path.relative(base, absolute).replaceAll('\\', '/')] : [];
  }).sort();
}

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function writeHeadBlob(temporaryRoot, relativePath) {
  assert.match(relativePath, /^dashboard-app\/(?:package(?:-lock)?\.json|vite\.config\.js|src\/[A-Za-z0-9._/-]+)$/);
  assert.equal(relativePath.includes('..'), false, `unsafe HEAD input path: ${relativePath}`);
  const destination = path.resolve(temporaryRoot, ...relativePath.split('/'));
  assert.equal(destination.startsWith(path.resolve(temporaryRoot) + path.sep), true, `HEAD input escaped temporary tree: ${relativePath}`);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.writeFileSync(destination, headBlob(relativePath));
}

function buildEnvironment(temporaryRoot) {
  const safeEntries = Object.entries(process.env).filter(([name]) => (
    !/^(?:VITE_|CORDIA_)/i.test(name)
    && !/(?:TOKEN|SECRET|PASSWORD|CREDENTIAL|API_KEY|ACCESS_KEY|PRIVATE_KEY)/i.test(name)
  ));
  return {
    ...Object.fromEntries(safeEntries),
    CI: 'true',
    NO_COLOR: '1',
    npm_config_audit: 'false',
    npm_config_cache: path.join(temporaryRoot, '.npm-cache'),
    npm_config_fund: 'false',
    npm_config_update_notifier: 'false',
  };
}

function runNpm(arguments_, cwd, temporaryRoot) {
  const command = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const result = childProcess.spawnSync(command, arguments_, {
    cwd,
    env: buildEnvironment(temporaryRoot),
    shell: process.platform === 'win32',
    stdio: 'inherit',
    windowsHide: true,
  });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, `${command} ${arguments_.join(' ')} failed with exit ${result.status}`);
}

function removeTemporaryTree(temporaryRoot) {
  const resolvedBase = path.resolve(os.tmpdir());
  const resolvedTarget = path.resolve(temporaryRoot);
  const relativeTarget = path.relative(resolvedBase, resolvedTarget);
  assert.notEqual(relativeTarget, '', 'refusing to remove the temporary-directory root');
  assert.equal(relativeTarget.startsWith('..') || path.isAbsolute(relativeTarget), false, 'temporary tree escaped the temporary-directory root');
  assert.equal(path.basename(resolvedTarget).startsWith(temporaryPrefix), true, 'unexpected temporary release directory');
  fs.rmSync(resolvedTarget, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
}

function verify() {
  const temporaryRoot = fs.mkdtempSync(path.join(os.tmpdir(), temporaryPrefix));
  try {
    const inputs = headInputs();
    assert.ok(inputs.length > 4, 'HEAD must contain the bounded dashboard input set');
    for (const input of inputs) writeHeadBlob(temporaryRoot, input);

    const dashboardRoot = path.join(temporaryRoot, 'dashboard-app');
    runNpm(['ci'], dashboardRoot, temporaryRoot);
    runNpm(['run', 'build'], dashboardRoot, temporaryRoot);

    const headManifest = headBlob('web/dashboard/build-provenance.json');
    const manifest = JSON.parse(headManifest.toString('utf8'));
    const expectedOutputs = ['build-provenance.json', ...manifest.outputs.map((output) => output.path)].sort();
    const rebuiltRoot = path.join(temporaryRoot, 'web', 'dashboard');
    assert.deepEqual(filesBelow(rebuiltRoot), expectedOutputs, 'clean HEAD rebuild emitted a different release file set');

    for (const output of expectedOutputs) {
      const relativePath = `web/dashboard/${output}`;
      const committed = headBlob(relativePath);
      const rebuilt = fs.readFileSync(path.join(rebuiltRoot, ...output.split('/')));
      assert.equal(
        rebuilt.equals(committed),
        true,
        `${relativePath} differs: HEAD ${sha256(committed)}, rebuilt ${sha256(rebuilt)}`,
      );
    }

    console.log(`dashboard release reproducibility verified from HEAD source ${manifest.source.sha256}`);
    for (const output of expectedOutputs) {
      console.log(`${sha256(headBlob(`web/dashboard/${output}`))}  web/dashboard/${output}`);
    }
  } finally {
    removeTemporaryTree(temporaryRoot);
  }
}

verify();
