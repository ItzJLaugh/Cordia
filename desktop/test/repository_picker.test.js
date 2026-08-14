const assert = require('node:assert/strict');
const test = require('node:test');

const { pickRepository } = require('../repository_picker');

test('returns null when the user cancels directory selection', async () => {
  const result = await pickRepository({
    showOpenDialog: async () => ({ canceled: true, filePaths: [] }),
  }, () => { throw new Error('must not inspect after cancellation'); });

  assert.equal(result, null);
});

test('passes exactly the one selected directory to the metadata-only inspector', async () => {
  const calls = [];
  const expected = { kind: 'local_repository', label: 'Cordia' };
  const result = await pickRepository({
    showOpenDialog: async (options) => {
      calls.push(options);
      return { canceled: false, filePaths: ['C:/projects/Cordia'] };
    },
  }, (selectedPath) => {
    assert.equal(selectedPath, 'C:/projects/Cordia');
    return expected;
  });

  assert.equal(result, expected);
  assert.deepEqual(calls, [{ properties: ['openDirectory'] }]);
});
