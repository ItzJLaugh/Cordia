const FIXED_ARGS = Object.freeze({
  status: ['status', '--porcelain=v1', '--branch'],
  pull: ['pull', '--ff-only'],
  push: ['push'],
});

function fixedArgs(operation) {
  if (typeof operation !== 'string' || !Object.hasOwn(FIXED_ARGS, operation)) {
    throw new Error('Unsupported Git operation.');
  }
  return [...FIXED_ARGS[operation]];
}

function run(repositoryPath, operation, execFile) {
  return new Promise((resolve, reject) => {
    execFile('git', fixedArgs(operation), {
      cwd: repositoryPath,
      shell: false,
      maxBuffer: 8192,
    }, (error, stdout) => {
      if (error) {
        reject(new Error('Git operation failed.'));
        return;
      }
      resolve(String(stdout || ''));
    });
  });
}

function parseStatus(stdout) {
  const lines = stdout.split(/\r?\n/);
  const header = lines[0] || '';
  const match = /^## (.+?)(?:\.\.\.([^\s]+))?(?: \[(.+)\])?$/.exec(header);
  const branchName = match?.[1] || null;
  const tracking = match?.[3] || '';
  const ahead = /(?:^|, )ahead (\d+)(?:,|$)/.exec(tracking);
  const behind = /(?:^|, )behind (\d+)(?:,|$)/.exec(tracking);

  return {
    branch: branchName?.startsWith('HEAD ') ? null : branchName,
    clean: lines.slice(1).every((line) => line === ''),
    ahead: ahead ? Number(ahead[1]) : 0,
    behind: behind ? Number(behind[1]) : 0,
    upstream: match?.[2] || null,
  };
}

async function status(repositoryPath, execFile) {
  return parseStatus(await run(repositoryPath, 'status', execFile));
}

module.exports = { fixedArgs, run, status };
