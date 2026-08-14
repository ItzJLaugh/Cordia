class RepositoryRegistry {
  constructor() {
    this.selectedPaths = new Map();
  }

  register(metadata, selectedPath) {
    this.selectedPaths.set(metadata.id, selectedPath);
    const { id, kind, label, path_label: pathLabel, git_root: gitRoot, branch } = metadata;
    const safeMetadata = { id, label };
    if (kind !== undefined) safeMetadata.kind = kind;
    if (pathLabel !== undefined) safeMetadata.path_label = pathLabel;
    if (gitRoot !== undefined) safeMetadata.git_root = gitRoot;
    if (branch !== undefined) safeMetadata.branch = branch;
    return safeMetadata;
  }

  resolve(id) {
    const selectedPath = this.selectedPaths.get(id);
    if (!selectedPath) throw new Error('Selected repository is unavailable.');
    return selectedPath;
  }
}

module.exports = { RepositoryRegistry };
