const assert = require('node:assert/strict');
const test = require('node:test');

const { fixedArgs, run, status } = require('../git_adapter');

function execFileResult(stdout, stderr = '') {
  return (bin, args, options, callback) => callback(null, stdout, stderr);
}

test('runs status with fixed no-shell argv', async () => {
  let invocation;
  const execFile = (bin, args, options, callback) => {
    invocation = [bin, args, options];
    callback(null, '## main...origin/main\n', '');
  };

  await run('C:/private/repository', 'status', execFile);

  assert.deepEqual(invocation, [
    'git',
    ['status', '--porcelain=v1', '--branch'],
    { cwd: 'C:/private/repository', shell: false, maxBuffer: 8192 },
  ]);
});

test('rejects arbitrary operations', () => {
  assert.throws(() => fixedArgs('reset --hard'), /Unsupported Git operation/);
  assert.throws(() => fixedArgs(['status']), /Unsupported Git operation/);
});

test('uses fixed argv for pull and push', () => {
  assert.deepEqual(fixedArgs('pull'), ['pull', '--ff-only']);
  assert.deepEqual(fixedArgs('push'), ['push']);
});

test('reduces Git failures to a bounded safe error', async () => {
  await assert.rejects(
    run('C:/private/repository', 'status', (_bin, _args, _options, callback) => {
      callback(new Error('fatal: a private remote URL and path'));
    }),
    { message: 'Git operation failed.' },
  );
});

test('parses clean and dirty repository status without exposing paths', async () => {
  const clean = await status('C:/private/repository', execFileResult('## main...origin/main\n'));
  const dirty = await status('C:/private/repository', execFileResult('## main...origin/main\n M README.md\n'));

  assert.deepEqual(clean, {
    branch: 'main', clean: true, ahead: 0, behind: 0, upstream: 'origin/main',
  });
  assert.deepEqual(dirty, {
    branch: 'main', clean: false, ahead: 0, behind: 0, upstream: 'origin/main',
  });
  assert.equal(Object.hasOwn(clean, 'path'), false);
  assert.equal(Object.hasOwn(dirty, 'path'), false);
});

test('parses ahead and behind counts', async () => {
  const result = await status('C:/private/repository', execFileResult(
    '## feature/test...origin/feature/test [ahead 2, behind 3]\n',
  ));

  assert.deepEqual(result, {
    branch: 'feature/test', clean: true, ahead: 2, behind: 3, upstream: 'origin/feature/test',
  });
});

test('parses detached HEAD and branch without upstream', async () => {
  const detached = await status('C:/private/repository', execFileResult('## HEAD (no branch)\n'));
  const noUpstream = await status('C:/private/repository', execFileResult('## topic\n'));

  assert.deepEqual(detached, {
    branch: null, clean: true, ahead: 0, behind: 0, upstream: null,
  });
  assert.deepEqual(noUpstream, {
    branch: 'topic', clean: true, ahead: 0, behind: 0, upstream: null,
  });
});
