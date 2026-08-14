const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const { discoverRepository } = require('../local_repository');

function fixtureDirectory(name) {
  return fs.mkdtempSync(path.join(os.tmpdir(), `cordia-${name}-`));
}

test('rejects a selected directory without a .git directory', () => {
  const directory = fixtureDirectory('not-git');
  try {
    assert.throws(() => discoverRepository(directory), /Select a Git repository directory/);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('returns Git metadata without an absolute path field', () => {
  const directory = fixtureDirectory('repository');
  fs.mkdirSync(path.join(directory, '.git'));
  try {
    const repository = discoverRepository(directory);
    assert.equal(repository.kind, 'local_repository');
    assert.equal(repository.git_root, true);
    assert.equal(repository.label, path.basename(directory));
    assert.equal(repository.path_label, path.basename(directory));
    assert.match(repository.id, /^local-repo:[a-f0-9]{16}$/);
    assert.equal(Object.hasOwn(repository, 'path'), false);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('accepts a Git worktree with a .git pointer file', () => {
  const directory = fixtureDirectory('worktree');
  const gitData = fixtureDirectory('git-data');
  fs.writeFileSync(path.join(directory, '.git'), `gitdir: ${gitData}\n`);
  fs.writeFileSync(path.join(gitData, 'HEAD'), 'ref: refs/heads/feature/desktop\n');
  try {
    const repository = discoverRepository(directory);
    assert.equal(repository.git_root, true);
    assert.equal(repository.branch, 'feature/desktop');
    assert.equal(Object.hasOwn(repository, 'path'), false);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
    fs.rmSync(gitData, { recursive: true, force: true });
  }
});
