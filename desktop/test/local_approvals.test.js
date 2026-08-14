const assert = require('node:assert/strict');
const test = require('node:test');

const { LocalApprovals } = require('../local_approvals');

function approvalFixture() {
  return { operation: 'push', repositoryId: 'local-repo:a', branch: 'main', upstream: 'origin/main' };
}

test('creates opaque five-minute approval ids without exposing descriptors', () => {
  const approvals = new LocalApprovals({ now: () => 1_000 });

  const approval = approvals.create(approvalFixture());

  assert.match(approval.id, /^local-git-approval:[a-z0-9]{32}$/);
  assert.deepEqual(Object.keys(approval).sort(), ['expiresAt', 'id']);
  assert.equal(approval.expiresAt, 301_000);
});

test('consumes an approved matching descriptor exactly once', () => {
  const approvals = new LocalApprovals({ now: () => 1_000 });
  const descriptor = approvalFixture();
  const { id } = approvals.create(descriptor);
  approvals.decide(id, true);

  assert.deepEqual(approvals.consume(id, descriptor, 1_001), descriptor);
  assert.throws(() => approvals.consume(id, descriptor, 1_002), { message: 'Local Git approval is not valid.' });
});

test('rejects pending, declined, expired, unknown, and mismatched approvals', () => {
  let clock = 1_000;
  const approvals = new LocalApprovals({ now: () => clock });
  const descriptor = approvalFixture();
  const cases = [
    ['pending', () => approvals.create(descriptor), 1_001],
    ['declined', () => {
      const approval = approvals.create(descriptor);
      approvals.decide(approval.id, false);
      return approval;
    }, 1_001],
    ['expired', () => {
      const approval = approvals.create(descriptor);
      approvals.decide(approval.id, true);
      return approval;
    }, 301_001],
    ['unknown', () => ({ id: 'local-git-approval:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' }), 1_001],
  ];

  for (const [_name, makeApproval, now] of cases) {
    const { id } = makeApproval();
    assert.throws(() => approvals.consume(id, descriptor, now), { message: 'Local Git approval is not valid.' });
  }

  const { id } = approvals.create(descriptor);
  approvals.decide(id, true);
  assert.throws(
    () => approvals.consume(id, { ...descriptor, branch: 'other' }, 1_001),
    { message: 'Local Git approval is not valid.' },
  );
  clock += 1;
});

test('decide rejects unknown ids and a prior decision cannot be changed', () => {
  const approvals = new LocalApprovals({ now: () => 1_000 });
  const { id } = approvals.create(approvalFixture());

  assert.throws(() => approvals.decide('local-git-approval:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', true), { message: 'Local Git approval is not valid.' });
  approvals.decide(id, false);
  assert.throws(() => approvals.decide(id, true), { message: 'Local Git approval is not valid.' });
});

test('rejects an approval at its exact expiry boundary', () => {
  const approvals = new LocalApprovals({ now: () => 1_000 });
  const descriptor = approvalFixture();
  const { id, expiresAt } = approvals.create(descriptor);
  approvals.decide(id, true);

  assert.throws(() => approvals.approvedDescriptor(id, expiresAt), { message: 'Local Git approval is not valid.' });
  assert.throws(() => approvals.consume(id, descriptor, expiresAt), { message: 'Local Git approval is not valid.' });
});
