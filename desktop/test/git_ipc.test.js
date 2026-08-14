const assert = require('node:assert/strict');
const test = require('node:test');

const { registerGitIpcHandlers } = require('../git_ipc');

test('native confirmation decline leaves the local approval unexecutable', async () => {
  const handlers = new Map();
  let decided;
  let executed = false;
  const gitSkills = {
    approvals: { decide(id, approved) { decided = { id, approved }; } },
    async preview() { return { operation: 'push', branch: 'main', approval: { id: 'local-git-approval:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', expiresAt: 301000 } }; },
    async execute() { executed = true; },
  };
  registerGitIpcHandlers({
    ipcMain: { handle(channel, handler) { handlers.set(channel, handler); } },
    dialog: { async showMessageBox() { return { response: 0 }; } },
    gitSkills,
  });

  const preview = await handlers.get('cordia-desktop:git-preview')({ sender: { getOwnerBrowserWindow: () => ({}) } }, 'local-repo:a', 'push');

  assert.equal(preview.operation, 'push');
  assert.equal(Object.hasOwn(preview, 'upstream'), false);
  assert.deepEqual(decided, { id: 'local-git-approval:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', approved: false });
  assert.equal(executed, false);
  assert.equal(handlers.has('cordia-desktop:git-execute'), true);
});
