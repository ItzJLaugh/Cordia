import assert from 'node:assert/strict'
import test from 'node:test'

import React from 'react'
import TestRenderer, { act } from 'react-test-renderer'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((pass, fail) => {
    resolve = pass
    reject = fail
  })
  return { promise, resolve, reject }
}

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

async function render(component) {
  const originalConsoleError = console.error
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  console.error = (...args) => {
    if (args[0] !== 'react-test-renderer is deprecated. See https://react.dev/warnings/react-test-renderer') {
      originalConsoleError(...args)
    }
  }
  let renderer
  try {
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(component))
    })
    return renderer
  } finally {
    console.error = originalConsoleError
  }
}

test('rendered sign out submits once, clears identity hints but retains device and responses, then navigates', async () => {
  const originals = new Map()
  const request = deferred()
  const requests = []
  const removedLocal = []
  const removedSession = []
  const navigations = []
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('window', { location: { replace: (path) => navigations.push(path) } }, originals)
  replaceGlobal('localStorage', {
    getItem: () => 'development-token',
    removeItem: (key) => removedLocal.push(key),
  }, originals)
  replaceGlobal('sessionStorage', {
    removeItem: (key) => removedSession.push(key),
  }, originals)
  replaceGlobal('fetch', (url, options) => {
    requests.push({ url, options })
    return request.promise
  }, originals)

  let renderer
  try {
    const module = await import('../src/SignOutControl.js').catch(() => null)
    assert.ok(module, 'the production sign-out control must be directly render-testable')
    renderer = await render(module.default)
    const button = renderer.root.findByType('button')
    assert.equal(button.children.join(''), 'Sign out')
    assert.equal(button.props.type, 'button')

    await act(async () => {
      button.props.onClick()
      button.props.onClick()
    })
    assert.deepEqual(requests, [{
      url: '/auth/logout',
      options: { method: 'POST', credentials: 'include' },
    }])
    assert.equal(renderer.root.findByType('button').props.disabled, true)
    assert.equal(renderer.root.findByType('button').children.join(''), 'Signing out…')
    assert.deepEqual(removedLocal, [])
    assert.deepEqual(removedSession, [])
    assert.deepEqual(navigations, [])

    await act(async () => {
      request.resolve({ ok: true, status: 200, json: async () => ({ ok: true }) })
      await request.promise
    })
    assert.deepEqual(removedLocal, ['cordia-dev-token', 'cordia-learner'])
    assert.deepEqual(removedSession, ['cordia-auth', 'cordia-user'])
    assert.equal(removedLocal.includes('cordia-device'), false)
    assert.equal(removedLocal.includes('cordia-responses'), false)
    assert.deepEqual(navigations, ['/'])
  } finally {
    if (renderer) await act(async () => { renderer.unmount() })
    restoreGlobals(originals)
  }
})

test('rendered sign out stays recoverable and bounded for rejected, non-ok, and malformed responses', async () => {
  const originals = new Map()
  const removed = []
  const navigations = []
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('window', { location: { replace: (path) => navigations.push(path) } }, originals)
  replaceGlobal('localStorage', { getItem: () => null, removeItem: (key) => removed.push(key) }, originals)
  replaceGlobal('sessionStorage', { removeItem: (key) => removed.push(key) }, originals)

  const failures = [
    async () => { throw new Error('authorization=Bearer private at C:\\private\\host') },
    async () => ({
      ok: false,
      status: 500,
      json: async () => ({ ok: false, error: 'authorization=private-server-detail' }),
    }),
    async () => ({ ok: true, status: 200, json: async () => ({ ok: false }) }),
  ]

  let module
  try {
    module = await import('../src/SignOutControl.js').catch(() => null)
    assert.ok(module, 'the production sign-out control must be directly render-testable')
    for (const fail of failures) {
      globalThis.fetch = fail
      const renderer = await render(module.default)
      try {
        await act(async () => {
          await renderer.root.findByType('button').props.onClick()
        })
        const button = renderer.root.findByType('button')
        assert.equal(button.props.disabled, false)
        assert.equal(button.children.join(''), 'Sign out')
        assert.equal(renderer.root.findByProps({ role: 'alert' }).children.join(''),
          'Cordia could not sign you out. Try again.')
        const visible = JSON.stringify(renderer.toJSON())
        for (const secret of ['authorization', 'Bearer', 'private', 'server-detail']) {
          assert.equal(visible.includes(secret), false, secret)
        }
        assert.deepEqual(removed, [])
        assert.deepEqual(navigations, [])
      } finally {
        await act(async () => { renderer.unmount() })
      }
    }
  } finally {
    restoreGlobals(originals)
  }
})
