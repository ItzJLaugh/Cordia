const CONDITIONS = new Set(['clean', 'incoming_changes', 'synchronized']);
const MUTATIONS = new Set(['pull', 'push']);
const INVALID_APPROVAL = 'Local Git approval is not valid.';

function safeStatus(status) {
  return {
    branch: status.branch,
    clean: status.clean,
    ahead: status.ahead,
    behind: status.behind,
  };
}

function matches(status, condition) {
  return (condition === 'clean' && status.clean)
    || (condition === 'incoming_changes' && status.behind > 0)
    || (condition === 'synchronized' && status.clean && status.ahead === 0 && status.behind === 0);
}

function boundedOptions(options = {}) {
  const intervalMs = options.intervalMs ?? 1000;
  const timeoutMs = options.timeoutMs ?? 10000;
  if (!Number.isInteger(intervalMs) || intervalMs < 250 || intervalMs > 2000) {
    throw new Error('Git wait interval must be between 250 and 2000 milliseconds.');
  }
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1000 || timeoutMs > 60000) {
    throw new Error('Git wait timeout must be between 1 and 60 seconds.');
  }
  return { intervalMs, timeoutMs };
}

class GitSkills {
  constructor({
    registry,
    adapter,
    now = () => Date.now(),
    sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
    approvals,
  }) {
    this.registry = registry;
    this.adapter = adapter;
    this.now = now;
    this.sleep = sleep;
    this.approvals = approvals;
  }

  async status(repositoryId) {
    return safeStatus(await this.internalStatus(repositoryId));
  }

  async internalStatus(repositoryId) {
    const selectedPath = this.registry.resolve(repositoryId);
    return this.adapter.status(selectedPath);
  }

  async wait(repositoryId, condition, options) {
    if (!CONDITIONS.has(condition)) throw new Error('Unsupported Git wait condition.');
    const { intervalMs, timeoutMs } = boundedOptions(options);
    let latestStatus;
    const deadlineMs = this.now() + timeoutMs;

    while (true) {
      latestStatus = await this.status(repositoryId);
      if (matches(latestStatus, condition)) {
        return { condition, matched: true, timed_out: false, status: latestStatus };
      }
      const remainingMs = deadlineMs - this.now();
      if (remainingMs <= 0) {
        return { condition, matched: false, timed_out: true, status: latestStatus };
      }
      await this.sleep(Math.min(intervalMs, remainingMs));
      if (this.now() >= deadlineMs) {
        return { condition, matched: false, timed_out: true, status: latestStatus };
      }
    }
  }

  async preview(repositoryId, operation) {
    if (typeof operation !== 'string' || !MUTATIONS.has(operation)) throw new Error('Unsupported Git operation.');
    const status = await this.internalStatus(repositoryId);
    if (!status.clean) throw new Error('Git working tree must be clean.');
    if (!status.branch || !status.upstream) throw new Error('Git branch must have an upstream.');
    const descriptor = { operation, repositoryId, branch: status.branch, upstream: status.upstream };
    if (!this.approvals) throw new Error(INVALID_APPROVAL);
    return {
      operation,
      branch: status.branch,
      approval: this.approvals.create(descriptor),
    };
  }

  async execute(approvalId) {
    if (!this.approvals) throw new Error(INVALID_APPROVAL);
    const descriptor = this.approvals.approvedDescriptor(approvalId, this.now());
    const status = await this.internalStatus(descriptor.repositoryId);
    if (!status.clean || status.branch !== descriptor.branch || status.upstream !== descriptor.upstream) {
      throw new Error(INVALID_APPROVAL);
    }
    this.approvals.consume(approvalId, descriptor, this.now());
    await this.adapter.run(this.registry.resolve(descriptor.repositoryId), descriptor.operation);
    return { operation: descriptor.operation, branch: descriptor.branch, completed: true };
  }
}

module.exports = { GitSkills };
