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

async function render(component, props, options = {}) {
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
      renderer = TestRenderer.create(React.createElement(component, props), options)
    })
    return renderer
  } finally {
    console.error = originalConsoleError
  }
}

test('opening the correction dialog labels it and moves focus to its first choice', async () => {
  const originals = new Map()
  let focused = 0
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('localStorage', { getItem: () => null }, originals)
  let renderer
  try {
    const { default: IntentCorrectionControl } = await import('../src/IntentCorrectionControl.js?focus-contract')
    renderer = await render(IntentCorrectionControl, {
      messages: [{ id: 1, who: 'cordia', text: 'Here is the draft.' }],
    }, {
      createNodeMock: (element) => (
        element.type === 'select' ? { focus: () => { focused += 1 } } : {}
      ),
    })

    await act(async () => {
      renderer.root.findByProps({ 'data-intent-correction-toggle': true }).props.onClick()
    })

    const dialog = renderer.root.findByProps({ role: 'dialog' })
    assert.equal(dialog.props['aria-labelledby'], 'intent-correction-title')
    assert.equal(dialog.props['aria-describedby'], 'intent-correction-description')
    assert.equal(renderer.root.findByProps({ id: 'intent-correction-title' }).children.join(''), 'Correct Cordia')
    assert.equal(focused, 1)
  } finally {
    if (renderer) await act(async () => { renderer.unmount() })
    restoreGlobals(originals)
  }
})

test('rendered intent correction records once and refreshes the same workspace before reporting success', async () => {
  const originals = new Map()
  const request = deferred()
  const requests = []
  const busy = []
  let refreshes = 0
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('localStorage', { getItem: () => null }, originals)
  replaceGlobal('fetch', (url, options) => {
    requests.push({ url, options })
    return request.promise
  }, originals)

  let renderer
  try {
    const module = await import('../src/IntentCorrectionControl.js').catch(() => null)
    assert.ok(module, 'the production intent-correction control must be directly render-testable')
    const operation = { current: '' }
    renderer = await render(module.default, {
      messages: [{ id: 1, who: 'cordia', text: 'Here is the draft.' }],
      readOnly: false,
      disabled: false,
      operation,
      onBusyChange: (value) => busy.push(value),
      refresh: async () => { refreshes += 1 },
    })

    await act(async () => {
      renderer.root.findByProps({ 'data-intent-correction-toggle': true }).props.onClick()
    })
    const select = renderer.root.findByProps({ name: 'category' })
    const correction = renderer.root.findByProps({ name: 'correction' })
    const effect = renderer.root.findByProps({ name: 'effect' })
    await act(async () => {
      select.props.onChange({ target: { value: 'needs_evidence' } })
      correction.props.onChange({ target: { value: 'Cite the inspection photographs.' } })
      effect.props.onChange({ target: { value: 'Include source links in future drafts.' } })
    })

    const form = renderer.root.findByType('form')
    await act(async () => {
      form.props.onSubmit({ preventDefault() {} })
      form.props.onSubmit({ preventDefault() {} })
    })
    assert.equal(requests.length, 1)
    assert.equal(operation.current, 'intent-correction')
    assert.deepEqual(busy, [true])
    assert.equal(renderer.root.findByProps({ type: 'submit' }).props.disabled, true)
    assert.equal(refreshes, 0)

    await act(async () => {
      request.resolve({
        ok: true,
        status: 200,
        json: async () => ({
          ok: true,
          artifacts: { 'runtime/fde-tasks.md': 'authorization=private-server-payload' },
        }),
      })
      await request.promise
      await new Promise((resolve) => setTimeout(resolve, 0))
    })

    assert.equal(refreshes, 1)
    assert.equal(operation.current, '')
    assert.deepEqual(busy, [true, false])
    assert.equal(renderer.root.findAllByType('form').length, 0)
    assert.equal(renderer.root.findByProps({ role: 'status' }).children.join(''),
      'Correction saved. Cordia refreshed this workspace guidance.')
    assert.equal(JSON.stringify(renderer.toJSON()).includes('private-server-payload'), false)
  } finally {
    if (renderer) await act(async () => { renderer.unmount() })
    restoreGlobals(originals)
  }
})

test('cancelling an intent correction discards the hidden draft before reopening', async () => {
  const originals = new Map()
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('localStorage', { getItem: () => null }, originals)
  let renderer
  try {
    const { default: IntentCorrectionControl } = await import('../src/IntentCorrectionControl.js?cancel-contract')
    renderer = await render(IntentCorrectionControl, {
      messages: [{ id: 1, who: 'cordia', text: 'Here is the draft.' }],
      readOnly: false,
    })
    await act(async () => {
      renderer.root.findByProps({ 'data-intent-correction-toggle': true }).props.onClick()
    })
    await act(async () => {
      renderer.root.findByProps({ name: 'category' }).props.onChange({ target: { value: 'wrong_format' } })
      renderer.root.findByProps({ name: 'correction' }).props.onChange({ target: { value: 'Use a table.' } })
      renderer.root.findByProps({ name: 'effect' }).props.onChange({ target: { value: 'Prefer tables next time.' } })
    })
    await act(async () => {
      renderer.root.findAllByType('button').find((button) => button.children.join('') === 'Cancel').props.onClick()
    })
    await act(async () => {
      renderer.root.findByProps({ 'data-intent-correction-toggle': true }).props.onClick()
    })
    assert.equal(renderer.root.findByProps({ name: 'category' }).props.value, '')
    assert.equal(renderer.root.findByProps({ name: 'correction' }).props.value, '')
    assert.equal(renderer.root.findByProps({ name: 'effect' }).props.value, '')
  } finally {
    if (renderer) await act(async () => { renderer.unmount() })
    restoreGlobals(originals)
  }
})

test('the correction control appears only after Cordia output and never in read-only Alidora', async () => {
  const originals = new Map()
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('localStorage', { getItem: () => null }, originals)
  let renderer
  try {
    const { default: IntentCorrectionControl } = await import('../src/IntentCorrectionControl.js?visibility-contract')
    renderer = await render(IntentCorrectionControl, {
      messages: [], readOnly: false,
    })
    assert.equal(renderer.root.findAllByProps({ 'data-intent-correction-toggle': true }).length, 0)
    await act(async () => { renderer.unmount() })

    renderer = await render(IntentCorrectionControl, {
      messages: [{ id: 1, who: 'cordia', text: 'Here is the draft.' }], readOnly: false,
    })
    assert.equal(renderer.root.findAllByProps({ 'data-intent-correction-toggle': true }).length, 1)
    await act(async () => { renderer.unmount() })

    renderer = await render(IntentCorrectionControl, {
      messages: [{ id: 1, who: 'cordia', text: 'Here is the draft.' }],
      readOnly: true,
    })
    assert.equal(renderer.root.findAllByProps({ 'data-intent-correction-toggle': true }).length, 0)
  } finally {
    if (renderer) await act(async () => { renderer.unmount() })
    restoreGlobals(originals)
  }
})

test('a failed correction stays editable and exposes only bounded recovery copy', async () => {
  const originals = new Map()
  const busy = []
  let refreshes = 0
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('localStorage', { getItem: () => null }, originals)
  replaceGlobal('fetch', async () => {
    throw new Error('authorization=Bearer private-value at C:\\private\\host')
  }, originals)
  let renderer
  try {
    const { default: IntentCorrectionControl } = await import('../src/IntentCorrectionControl.js?failure-contract')
    const operation = { current: '' }
    renderer = await render(IntentCorrectionControl, {
      messages: [{ id: 1, who: 'cordia', text: 'Here is the draft.' }],
      operation,
      onBusyChange: (value) => busy.push(value),
      refresh: async () => { refreshes += 1 },
    })
    await act(async () => {
      renderer.root.findByProps({ 'data-intent-correction-toggle': true }).props.onClick()
    })
    await act(async () => {
      renderer.root.findByProps({ name: 'category' }).props.onChange({ target: { value: 'wrong_format' } })
      renderer.root.findByProps({ name: 'correction' }).props.onChange({ target: { value: 'Use a table.' } })
      renderer.root.findByProps({ name: 'effect' }).props.onChange({ target: { value: 'Prefer tables next time.' } })
    })
    await act(async () => {
      await renderer.root.findByType('form').props.onSubmit({ preventDefault() {} })
    })

    assert.equal(renderer.root.findByProps({ name: 'correction' }).props.value, 'Use a table.')
    assert.equal(renderer.root.findByProps({ name: 'effect' }).props.value, 'Prefer tables next time.')
    assert.equal(renderer.root.findByProps({ role: 'alert' }).children.join(''),
      'Cordia is unavailable right now. Your correction is still here.')
    assert.equal(operation.current, '')
    assert.deepEqual(busy, [true, false])
    assert.equal(refreshes, 0)
    for (const privateValue of ['authorization', 'Bearer', 'private-value', 'C:\\private']) {
      assert.equal(JSON.stringify(renderer.toJSON()).includes(privateValue), false, privateValue)
    }
  } finally {
    if (renderer) await act(async () => { renderer.unmount() })
    restoreGlobals(originals)
  }
})

test('a saved correction reports a reload when canonical workspace refresh fails', async () => {
  const originals = new Map()
  let requests = 0
  replaceGlobal('location', { hostname: 'cordia.example.test' }, originals)
  replaceGlobal('localStorage', { getItem: () => null }, originals)
  replaceGlobal('fetch', async () => {
    requests += 1
    return { ok: true, status: 200, json: async () => ({ ok: true }) }
  }, originals)
  let renderer
  try {
    const { default: IntentCorrectionControl } = await import('../src/IntentCorrectionControl.js?refresh-failure-contract')
    renderer = await render(IntentCorrectionControl, {
      messages: [{ id: 1, who: 'cordia', text: 'Here is the draft.' }],
      refresh: async () => { throw new Error('token=private-refresh-detail') },
    })
    await act(async () => {
      renderer.root.findByProps({ 'data-intent-correction-toggle': true }).props.onClick()
    })
    await act(async () => {
      renderer.root.findByProps({ name: 'category' }).props.onChange({ target: { value: 'wrong_audience' } })
      renderer.root.findByProps({ name: 'correction' }).props.onChange({ target: { value: 'Write for operators.' } })
      renderer.root.findByProps({ name: 'effect' }).props.onChange({ target: { value: 'Use operational language.' } })
    })
    await act(async () => {
      await renderer.root.findByType('form').props.onSubmit({ preventDefault() {} })
    })

    assert.equal(requests, 1)
    assert.equal(renderer.root.findAllByType('form').length, 0)
    assert.equal(renderer.root.findByProps({ role: 'status' }).children.join(''),
      'Correction saved. Reload this workspace to see the refreshed guidance.')
    assert.equal(JSON.stringify(renderer.toJSON()).includes('private-refresh-detail'), false)
  } finally {
    if (renderer) await act(async () => { renderer.unmount() })
    restoreGlobals(originals)
  }
})
