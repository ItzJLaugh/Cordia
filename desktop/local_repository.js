const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

function gitMetadataDirectory(gitPath) {
  const stat = fs.statSync(gitPath, { throwIfNoEntry: false });
  if (stat?.isDirectory()) return gitPath;
  if (!stat?.isFile()) return null;
  const pointer = fs.readFileSync(gitPath, 'utf8').trim();
  const match = /^gitdir:\s*(.+)$/.exec(pointer);
  return match ? path.resolve(path.dirname(gitPath), match[1]) : null;
}

function branchName(gitDirectory) {
  try {
    const head = fs.readFileSync(path.join(gitDirectory, 'HEAD'), 'utf8').trim();
    const match = /^ref: refs\/heads\/(.+)$/.exec(head);
    return match ? match[1] : null;
  } catch {
    return null;
  }
}

function opaqueId(selectedPath) {
  return `local-repo:${crypto.createHash('sha256').update(path.resolve(selectedPath)).digest('hex').slice(0, 16)}`;
}

function discoverRepository(selectedPath) {
  const resolved = path.resolve(String(selectedPath || ''));
  const gitDirectory = path.join(resolved, '.git');
  const metadataDirectory = gitMetadataDirectory(gitDirectory);
  if (!metadataDirectory) {
    throw new Error('Select a Git repository directory.');
  }
  const label = path.basename(resolved);
  return {
    kind: 'local_repository',
    id: opaqueId(resolved),
    label,
    path_label: label,
    git_root: true,
    branch: branchName(metadataDirectory),
  };
}

module.exports = { discoverRepository };
