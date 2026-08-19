const assert = require('node:assert/strict')
const test = require('node:test')

const navigation = require('../assets/workspace-navigation')
const generation = require('../assets/cordia-workspace-generation')


test('generation uses one fixed authenticated request and safe primary navigation', async () => {
  const calls = []
  const result = await generation.generate({
    fetch: async (...args) => {
      calls.push(args)
      return {
        ok: true,
        json: async () => ({ ok: true, id: 'workspace-1', created: true }),
      }
    },
    navigation,
  })

  assert.deepEqual(calls, [[
    '/surveyor/workspace/generate',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: '{}',
    },
  ]])
  assert.deepEqual(result, {
    id: 'workspace-1',
    href: '/dashboard/?workspace=workspace-1',
    created: true,
  })
})


test('generation rejects untrusted response shapes and destinations', async () => {
  const payloads = [
    null,
    { ok: true, id: 'workspace-1', created: true, url: 'https://attacker.example' },
    { ok: true, id: 'github_pat_abcdefghijklmnopqrstuvwxyz012345', created: true },
    { ok: true, id: 'C:\\private\\workspace', created: true },
    { ok: true, id: 'workspace-1', created: 'yes' },
  ]
  for (const payload of payloads) {
    await assert.rejects(
      generation.generate({
        fetch: async () => ({ ok: true, json: async () => payload }),
        navigation,
      }),
      /generation failed/
    )
  }
})


test('generation rejects transport, HTTP, and invalid JSON failures', async () => {
  await assert.rejects(generation.generate({
    fetch: async () => { throw new Error('token=PRIVATE') },
    navigation,
  }), /generation failed/)
  await assert.rejects(generation.generate({
    fetch: async () => ({ ok: false, json: async () => ({ ok: false, error: 'private' }) }),
    navigation,
  }), /generation failed/)
  await assert.rejects(generation.generate({
    fetch: async () => ({ ok: true, json: async () => { throw new Error('invalid') } }),
    navigation,
  }), /generation failed/)
})
