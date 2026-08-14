const { randomBytes } = require('node:crypto');
const { isDeepStrictEqual } = require('node:util');

const INVALID_APPROVAL = 'Local Git approval is not valid.';
const APPROVAL_LIFETIME_MS = 5 * 60 * 1000;

class LocalApprovals {
  constructor({ now = () => Date.now() } = {}) {
    this.now = now;
    this.records = new Map();
  }

  create(descriptor) {
    const id = `local-git-approval:${randomBytes(16).toString('hex')}`;
    const expiresAt = this.now() + APPROVAL_LIFETIME_MS;
    this.records.set(id, { descriptor: structuredClone(descriptor), expiresAt, state: 'pending' });
    return { id, expiresAt };
  }

  decide(id, approved) {
    const record = this.records.get(id);
    if (!record || record.state !== 'pending') throw new Error(INVALID_APPROVAL);
    record.state = approved === true ? 'approved' : 'declined';
  }

  approvedDescriptor(id, now = this.now()) {
    const record = this.records.get(id);
    if (!record || record.state !== 'approved' || now >= record.expiresAt) throw new Error(INVALID_APPROVAL);
    return structuredClone(record.descriptor);
  }

  consume(id, descriptor, now = this.now()) {
    const record = this.records.get(id);
    if (!record || record.state !== 'approved' || now >= record.expiresAt || !isDeepStrictEqual(record.descriptor, descriptor)) {
      throw new Error(INVALID_APPROVAL);
    }
    record.state = 'consumed';
    return structuredClone(record.descriptor);
  }
}

module.exports = { APPROVAL_LIFETIME_MS, INVALID_APPROVAL, LocalApprovals };
