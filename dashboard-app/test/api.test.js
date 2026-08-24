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

test('postRun exposes only the fixed revisioned idempotent Surveyor turn request', async () => {
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
    assert.deepEqual(await postRun('workspace-1', 4, `  ${'x'.repeat(6100)}  `, 'turn-abc123'), { ok: true, output: 'Ready' })
    assert.equal(requests.length, 1)
    assert.equal(requests[0].url, '/surveyor/run')
    assert.deepEqual(requests[0].options, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ id: 'workspace-1', revision: 4, message: 'x'.repeat(6000), idempotency_key: 'turn-abc123' }),
    })
    const storeId = '3b92e3b42cf94d96824322b7e33b07db'
    await postRun(storeId, 0, 'Review this', 'turn-abc124')
    assert.equal(JSON.parse(requests[1].options.body).id, storeId)
    await assert.rejects(postRun('C:\\private\\workspace', 0, 'Review this', 'turn-abc125'), /Invalid workspace request/)
    await assert.rejects(postRun('C:drive-relative', 0, 'Review this', 'turn-abc125'), /Invalid workspace request/)
    for (const credentialId of [
      'sk-abcdefghijk',
      'ghp_abcdefghijklmnopqrstuvwxyz',
      'github_pat_abcdefghijklmnopqrstuvwxyz0123456789',
      'AKIA1234567890ABCDEF',
      'token.secret-value',
    ]) {
      await assert.rejects(postRun(credentialId, 0, 'Review this', 'turn-abc125'), /Invalid workspace request/, credentialId)
    }
    assert.equal(requests.length, 2)
  } finally {
    restoreGlobals(originals)
  }
})

test('postSkillExecute exposes only the fixed skill route with one registered-looking id', async () => {
  const originals = new Map()
  const requests = []
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('localStorage', { getItem: () => null }, originals)
  replaceGlobal('fetch', async (url, options) => {
    requests.push({ url, options })
    return { ok: true, status: 200, json: async () => ({
      ok: true,
      skill: { name: 'Untrusted nested name', prompt: 'must not cross into the transcript' },
      result: { token: 'must not cross into renderer state' },
    }) }
  }, originals)

  try {
    const api = await import('../src/api.js?skill-execute-contract')
    assert.equal(typeof api.postSkillExecute, 'function')
    assert.equal((await api.postSkillExecute('github_repository_review')).ok, true)
    assert.deepEqual(requests, [{
      url: '/surveyor/skill/execute',
      options: {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ id: 'github_repository_review' }),
      },
    }])
    await assert.rejects(api.postSkillExecute('C:\\private\\skill'), /Invalid skill request/)
    await assert.rejects(api.postSkillExecute('token:secret'), /Invalid skill request/)
    await assert.rejects(api.postSkillExecute('GitHub_Repository_Review'), /Invalid skill request/)
    for (const credentialId of [
      'sk-abcdefghijk',
      'ghp_abcdefghijklmnopqrstuvwxyz',
      'github_pat_abcdefghijklmnopqrstuvwxyz0123456789',
      'AKIA1234567890ABCDEF',
      'token.secret-value',
    ]) {
      await assert.rejects(api.postSkillExecute(credentialId), /Invalid skill request/, credentialId)
    }
    assert.equal(requests.length, 1)
  } finally {
    restoreGlobals(originals)
  }
})

test('postLogout exposes only the fixed cookie-authenticated sign-out request', async () => {
  const originals = new Map()
  const requests = []
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('localStorage', { getItem: () => 'must-not-be-sent' }, originals)
  replaceGlobal('fetch', async (url, options) => {
    requests.push({ url, options })
    return { ok: true, status: 200, json: async () => ({ ok: true }) }
  }, originals)

  try {
    const api = await import('../src/api.js?logout-contract')
    assert.equal(typeof api.postLogout, 'function')
    assert.deepEqual(await api.postLogout(), { ok: true })
    assert.deepEqual(requests, [{
      url: '/auth/logout',
      options: {
        method: 'POST',
        credentials: 'include',
      },
    }])
  } finally {
    restoreGlobals(originals)
  }
})

test('postIntentMiss exposes one fixed bounded structured correction request', async () => {
  const originals = new Map()
  const requests = []
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('localStorage', { getItem: () => 'development-token' }, originals)
  replaceGlobal('fetch', async (url, options) => {
    requests.push({ url, options })
    return { ok: true, status: 200, json: async () => ({ ok: true, artifacts: { private: 'ignored' } }) }
  }, originals)

  try {
    const api = await import('../src/api.js?intent-miss-contract')
    assert.equal(typeof api.postIntentMiss, 'function')
    assert.equal((await api.postIntentMiss(
      'wrong_audience', `  ${'c'.repeat(700)}  `, `  ${'e'.repeat(700)}  `,
    )).ok, true)
    assert.deepEqual(requests, [{
      url: '/surveyor/intent-miss',
      options: {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer development-token',
        },
        credentials: 'include',
        body: JSON.stringify({
          category: 'wrong_audience',
          correction: 'c'.repeat(600),
          effect: 'e'.repeat(600),
        }),
      },
    }])

    for (const values of [
      ['invented', 'Use evidence.', 'Cite evidence.'],
      ['needs_evidence', '', 'Cite evidence.'],
      ['needs_evidence', 'Use evidence.', ''],
    ]) await assert.rejects(api.postIntentMiss(...values), /Invalid correction request/)
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
    await assert.rejects(postRun('workspace-1', 0, 'Review this', 'turn-abc123'), (error) => {
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

test('only the exact bounded revision conflict response is retryable', async () => {
  const originals = new Map()
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('localStorage', { getItem: () => null }, originals)

  try {
    const { apiErrorKind, postRun } = await import('../src/api.js?revision-conflict-contract')
    replaceGlobal('fetch', async () => ({
      ok: false, status: 409, json: async () => ({ ok: false, error: 'revision_conflict' }),
    }), originals)
    await assert.rejects(postRun('workspace-1', 4, 'Connect Drive', 'turn-fixed'), (error) => {
      assert.equal(apiErrorKind(error), 'revision-conflict')
      assert.equal(error.definitive, false)
      return true
    })

    globalThis.fetch = async () => ({
      ok: false, status: 409, json: async () => ({ ok: false, error: 'revision_conflict', detail: 'untrusted' }),
    })
    await assert.rejects(postRun('workspace-1', 4, 'Connect Drive', 'turn-fixed'), (error) => {
      assert.equal(apiErrorKind(error), 'error')
      assert.equal(error.definitive, true)
      return true
    })
  } finally {
    restoreGlobals(originals)
  }
})

test('only the exact usage-limit response is classified and exposed', async () => {
  const originals = new Map()
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('localStorage', { getItem: () => null }, originals)
  const fixed = {
    ok: false,
    error: 'Free agent actions used. Upgrade to continue.',
    code: 'usage_limit',
    used: 10,
    limit: 10,
  }

  try {
    const { apiErrorKind, postRun } = await import('../src/api.js?usage-limit-contract')
    replaceGlobal('fetch', async () => ({
      ok: false, status: 402, json: async () => fixed,
    }), originals)
    await assert.rejects(postRun('workspace-1', 4, 'Connect Drive', 'turn-fixed'), (error) => {
      assert.equal(apiErrorKind(error), 'usage-limit')
      assert.equal(error.message, fixed.error)
      assert.equal(error.definitive, true)
      return true
    })

    for (const body of [
      { ...fixed, detail: 'untrusted' },
      { ...fixed, used: 9 },
      { ...fixed, limit: '10' },
      { ok: false, error: 'payment required' },
    ]) {
      globalThis.fetch = async () => ({ ok: false, status: 402, json: async () => body })
      await assert.rejects(postRun('workspace-1', 4, 'Connect Drive', 'turn-fixed'), (error) => {
        assert.equal(apiErrorKind(error), 'error')
        assert.equal(error.definitive, true)
        return true
      })
    }
  } finally {
    restoreGlobals(originals)
  }
})
