import assert from 'node:assert/strict'
import test from 'node:test'

function replaceGlobal(name, value, originals) {
  originals.set(name, Object.getOwnPropertyDescriptor(globalThis, name))
  Object.defineProperty(globalThis, name, { configurable: true, writable: true, value })
}

function restoreGlobals(originals) {
  for (const [name, descriptor] of originals) {
    if (descriptor) Object.defineProperty(globalThis, name, descriptor)
    else delete globalThis[name]
  }
}

test('postRun exposes only the fixed Surveyor run request with a bounded input', async () => {
  const originals = new Map()
  const requests = []
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('localStorage', { getItem: () => null }, originals)
  replaceGlobal('fetch', async (url, options) => {
    requests.push({ url, options })
    return { ok: true, status: 200, json: async () => ({ ok: true, output: 'Ready' }) }
  }, originals)

  try {
    const { postRun } = await import('../src/api.js?post-run-contract')
    assert.deepEqual(await postRun('workspace-1', `  ${'x'.repeat(6100)}  `), { ok: true, output: 'Ready' })
    assert.equal(requests.length, 1)
    assert.equal(requests[0].url, '/surveyor/run')
    assert.deepEqual(requests[0].options, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ id: 'workspace-1', input: 'x'.repeat(6000) }),
    })
    await assert.rejects(postRun('C:\\private\\workspace', 'Review this'), /Invalid workspace request/)
    assert.equal(requests.length, 1)
  } finally {
    restoreGlobals(originals)
  }
})

test('API errors distinguish signed-out, rate-limited, and offline states without leaking transport details', async () => {
  const originals = new Map()
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('localStorage', { getItem: () => null }, originals)

  try {
    const { apiErrorKind, getApi, postRun } = await import('../src/api.js?state-contract')

    replaceGlobal('fetch', async () => ({
      ok: false, status: 401, json: async () => ({ ok: false, error: 'sign in required' }),
    }), originals)
    await assert.rejects(getApi('/surveyor/workspace?id=workspace-1'), (error) => {
      assert.equal(apiErrorKind(error), 'signed-out')
      assert.equal(error.message, 'sign in required')
      return true
    })

    globalThis.fetch = async () => ({
      ok: false, status: 429, json: async () => ({ ok: false, error: 'token=private-rate-detail' }),
    })
    await assert.rejects(postRun('workspace-1', 'Review this'), (error) => {
      assert.equal(apiErrorKind(error), 'rate-limit')
      assert.equal(error.message, 'Request failed')
      return true
    })

    globalThis.fetch = async () => { throw new Error('offline at C:\\private\\host') }
    await assert.rejects(getApi('/surveyor/activity'), (error) => {
      assert.equal(apiErrorKind(error), 'offline')
      assert.equal(error.message, 'Request failed')
      return true
    })
  } finally {
    restoreGlobals(originals)
  }
})
