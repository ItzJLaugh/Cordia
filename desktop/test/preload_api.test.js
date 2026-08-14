const assert = require('node:assert/strict');
const test = require('node:test');

const { desktopApi } = require('../preload_api');

test('exposes only typed desktop operations to the renderer', async () => {
  const calls = [];
  const api = desktopApi({
    invoke(channel, ...args) {
      calls.push([channel, args]);
      if (channel === 'cordia-desktop:runtime-info') {
        return Promise.resolve({ platform: 'win32', version: '0.1.0' });
      }
      if (channel === 'cordia-desktop:pick-repository') {
        return Promise.resolve({ kind: 'local_repository', label: 'Cordia' });
      }
      if (channel === 'cordia-desktop:git-status') {
        return Promise.resolve({ branch: 'main', clean: true, ahead: 0, behind: 0 });
      }
      if (channel === 'cordia-desktop:git-wait') {
        return Promise.resolve({ condition: 'clean', matched: true, timed_out: false, status: { branch: 'main', clean: true, ahead: 0, behind: 0 } });
      }
      if (channel === 'cordia-desktop:git-preview') {
        return Promise.resolve({ operation: 'push', branch: 'main', approval: { id: 'local-git-approval:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', expiresAt: 301000 } });
      }
      if (channel === 'cordia-desktop:git-execute') {
        return Promise.resolve({ operation: 'push', branch: 'main', completed: true });
      }
      throw new Error(`Unexpected channel: ${channel}`);
    },
  });

  assert.deepEqual(Object.keys(api), ['getRuntimeInfo', 'pickRepository', 'gitStatus', 'gitWait', 'gitPreview', 'gitExecute']);
  assert.deepEqual(await api.getRuntimeInfo(), { platform: 'win32', version: '0.1.0' });
  assert.deepEqual(await api.pickRepository(), { kind: 'local_repository', label: 'Cordia' });
  assert.deepEqual(await api.gitStatus('local-repo:a'), { branch: 'main', clean: true, ahead: 0, behind: 0 });
  assert.deepEqual(await api.gitWait('local-repo:a', 'clean'), { condition: 'clean', matched: true, timed_out: false, status: { branch: 'main', clean: true, ahead: 0, behind: 0 } });
  assert.deepEqual(await api.gitPreview('local-repo:a', 'push'), { operation: 'push', branch: 'main', approval: { id: 'local-git-approval:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', expiresAt: 301000 } });
  assert.deepEqual(await api.gitExecute('local-git-approval:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), { operation: 'push', branch: 'main', completed: true });
  assert.deepEqual(calls, [
    ['cordia-desktop:runtime-info', []],
    ['cordia-desktop:pick-repository', []],
    ['cordia-desktop:git-status', ['local-repo:a']],
    ['cordia-desktop:git-wait', ['local-repo:a', 'clean']],
    ['cordia-desktop:git-preview', ['local-repo:a', 'push']],
    ['cordia-desktop:git-execute', ['local-git-approval:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa']],
  ]);
});
