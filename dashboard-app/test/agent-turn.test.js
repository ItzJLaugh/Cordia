import assert from 'node:assert/strict'
import test from 'node:test'
import React, { useRef, useState } from 'react'
import TestRenderer, { act } from 'react-test-renderer'
import { createServer } from 'vite'

import { agentTurnModel, assistantGreeting, assistantRevisionConflict } from '../src/workspace-view.js'

test('a proposed connector accepts the fixed server copy without claiming connected', () => {
  const next = agentTurnModel({ ok: true, speech: 'I prepared a connector setup card.', revision: 5,
    action: { kind: 'propose_connector', state: 'setup_required',
      connector_id: 'issue_tracker', setup_kind: 'api_key' } })
  assert.deepEqual(next, {
    text: 'I prepared a connector setup card.', revision: 5,
    action: { kind: 'propose_connector', state: 'setup_required',
      connector_id: 'issue_tracker', setup_kind: 'api_key', label: 'Set up issue tracker' },
  })
  assert.equal(JSON.stringify(next).includes('Connected'), false)
})

test('agent turn model admits only the safe canonical response shape', () => {
  assert.deepEqual(agentTurnModel({ ok: true, speech: 'Hello.', action: null, revision: 0 }), {
    text: 'Hello.', action: null, revision: 0,
  })
  for (const bad of [
    { ok: true, speech: 'Hello.', action: null, revision: 0, secret_ref: 'nope' },
    { ok: true, speech: 'Hello.', action: null, revision: 0, providerSpeech: 'Provider sentinel prose.' },
    { ok: true, speech: 'C:\\private', action: null, revision: 0 },
    { ok: true, speech: 'Hello.', action: { kind: 'shell', state: 'run' }, revision: 0 },
  ]) assert.equal(agentTurnModel(bad), null)
})

test('the truthful empty-workspace greeting depends only on compiled memory truth', () => {
  assert.equal(assistantGreeting([], true, false),
    'I have your saved profile calibration and workspace memory. What would you like to accomplish?')
  assert.equal(assistantGreeting([], false, false), 'What would you like to accomplish?')
  assert.equal(assistantGreeting([], '   ', false), 'What would you like to accomplish?')
  assert.equal(assistantGreeting([], true, true), 'What would you like to accomplish?')
  assert.equal(assistantGreeting([{ who: 'cordia', text: 'Model text' }], true, false), '')
})

test('revision conflict restores the draft and retains the turn identity', () => {
  const failed = assistantRevisionConflict({
    transcript: [{ id: 'pending-1', who: 'you', text: 'Connect Drive' }],
    draft: '', note: '', busy: true,
    pending: { id: 'pending-1', text: 'Connect Drive', idempotencyKey: 'turn-fixed' },
  }, 'Workspace changed. Review it and retry.')
  assert.deepEqual(failed, {
    transcript: [], draft: 'Connect Drive', note: 'Workspace changed. Review it and retry.', busy: false,
    pending: null, retry: { text: 'Connect Drive', idempotencyKey: 'turn-fixed' },
  })
})

test('rendered Assistant stays locked until a deferred conflict refresh applies the new revision', async () => {
  const originals = new Map()
  for (const [name, value] of Object.entries({ location: { hostname: 'cordia.example.test' },
    localStorage: { getItem: () => null }, document: { activeElement: null } })) {
    originals.set(name, Object.getOwnPropertyDescriptor(globalThis, name))
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value })
  }
  const originalNow = Date.now
  Date.now = () => Number.parseInt('fixed', 36)
  const requests = []; let refreshes = 0; let resolveRefresh
  Object.defineProperty(globalThis, 'fetch', { configurable: true, writable: true, value: async (_url, options) => {
    requests.push(JSON.parse(options.body))
    if (requests.length === 1) return { ok: false, status: 409,
      json: async () => ({ ok: false, error: 'revision_conflict' }) }
    return { ok: true, status: 200, json: async () => ({ ok: true,
      speech: 'I prepared a connector setup card.', revision: 5,
      action: { kind: 'propose_connector', state: 'setup_required', connector_id: 'drive', setup_kind: 'api_key' } }) }
  } })
  const vite = await createServer({ configFile: false, server: { middlewareMode: true } })
  const module = await vite.ssrLoadModule('/src/WorkspaceView.jsx')
  const operation = { current: '' }; let renderer; globalThis.IS_REACT_ACT_ENVIRONMENT = true
  function Harness() {
    const [state, setState] = useState({ transcript: [], draft: 'Connect Drive', note: '', busy: false, pending: null, action: null })
    const [revision, setRevision] = useState(4)
    const id = useRef(0)
    return React.createElement(module.Assistant, { workspaceId: 'workspace-1', workspaceRevision: revision,
      enabled: true, readOnly: false, state, setState, nextId: () => ++id.current, operationRef: operation,
      refresh: async () => {
        refreshes += 1
        await new Promise((resolve) => { resolveRefresh = resolve })
        setRevision(5)
      } })
  }
  const priorConsoleError = console.error; console.error = () => {}
  try {
    await act(async () => { renderer = TestRenderer.create(React.createElement(Harness)) })
    const form = () => renderer.root.findByProps({ className: 'composer' })
    await act(async () => { form().props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    assert.equal(refreshes, 1)
    assert.equal(requests.length, 1)
    assert.equal(operation.current, 'assistant')
    await act(async () => { form().props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    assert.equal(requests.length, 1)
    await act(async () => {
      resolveRefresh()
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
    assert.equal(operation.current, '')
    assert.equal(JSON.stringify(renderer.toJSON()).includes('Workspace changed. Review the refreshed workspace and retry.'), true)
    await act(async () => { form().props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    assert.equal(requests.length, 2)
    assert.deepEqual(requests.map(({ revision, idempotency_key }) => ({ revision, idempotency_key })), [
      { revision: 4, idempotency_key: 'turn-fixed-1' },
      { revision: 5, idempotency_key: 'turn-fixed-1' },
    ])
  } finally {
    if (renderer) await act(async () => { renderer.unmount() })
    console.error = priorConsoleError; Date.now = originalNow; await vite.close()
    for (const [name, descriptor] of originals) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor)
      else delete globalThis[name]
    }
  }
})

test('rendered Assistant fails closed when a deferred conflict refresh rejects', async () => {
  const originals = new Map()
  for (const [name, value] of Object.entries({ location: { hostname: 'cordia.example.test' },
    localStorage: { getItem: () => null }, document: { activeElement: null } })) {
    originals.set(name, Object.getOwnPropertyDescriptor(globalThis, name))
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value })
  }
  const originalNow = Date.now
  Date.now = () => Number.parseInt('fixed', 36)
  const requests = []; let refreshes = 0; let rejectRefresh
  Object.defineProperty(globalThis, 'fetch', { configurable: true, writable: true, value: async (_url, options) => {
    requests.push(JSON.parse(options.body))
    if (requests.length === 1) return { ok: false, status: 409,
      json: async () => ({ ok: false, error: 'revision_conflict' }) }
    return { ok: true, status: 200, json: async () => ({ ok: true, speech: 'Drive is ready.', revision: 4, action: null }) }
  } })
  const vite = await createServer({ configFile: false, server: { middlewareMode: true } })
  const module = await vite.ssrLoadModule('/src/WorkspaceView.jsx')
  const operation = { current: '' }; let renderer; globalThis.IS_REACT_ACT_ENVIRONMENT = true
  function Harness() {
    const [state, setState] = useState({ transcript: [], draft: 'Connect Drive', note: '', busy: false, pending: null, action: null })
    const id = useRef(0)
    return React.createElement(module.Assistant, { workspaceId: 'workspace-1', workspaceRevision: 4,
      enabled: true, readOnly: false, state, setState, nextId: () => ++id.current, operationRef: operation,
      refresh: async () => {
        refreshes += 1
        await new Promise((_resolve, reject) => { rejectRefresh = reject })
      } })
  }
  const priorConsoleError = console.error; console.error = () => {}
  try {
    await act(async () => { renderer = TestRenderer.create(React.createElement(Harness)) })
    const form = () => renderer.root.findByProps({ className: 'composer' })
    await act(async () => { form().props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    assert.equal(refreshes, 1)
    assert.equal(requests.length, 1)
    assert.equal(operation.current, 'assistant')
    await act(async () => { form().props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    assert.equal(requests.length, 1)
    await act(async () => {
      rejectRefresh(new Error('refresh unavailable'))
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
    assert.equal(JSON.stringify(renderer.toJSON()).includes('Workspace refresh failed. Reload before retrying.'), true)
    await act(async () => { form().props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    assert.equal(requests.length, 1)
    assert.equal(operation.current, 'assistant')
  } finally {
    if (renderer) await act(async () => { renderer.unmount() })
    console.error = priorConsoleError; Date.now = originalNow; await vite.close()
    for (const [name, descriptor] of originals) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor)
      else delete globalThis[name]
    }
  }
})

test('rendered Assistant reuses retry identity for unchanged trimmed text and replaces it after an edit', async () => {
  const originals = new Map()
  for (const [name, value] of Object.entries({ location: { hostname: 'cordia.example.test' },
    localStorage: { getItem: () => null }, document: { activeElement: null } })) {
    originals.set(name, Object.getOwnPropertyDescriptor(globalThis, name))
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value })
  }
  const originalNow = Date.now
  Date.now = () => Number.parseInt('fixed', 36)
  const requests = []
  Object.defineProperty(globalThis, 'fetch', { configurable: true, writable: true, value: async (_url, options) => {
    requests.push(JSON.parse(options.body))
    if (requests.length === 2) return { ok: false, status: 500,
      json: async () => ({ ok: false, error: 'provider failed' }) }
    throw new Error('connection lost')
  } })
  const vite = await createServer({ configFile: false, server: { middlewareMode: true } })
  const module = await vite.ssrLoadModule('/src/WorkspaceView.jsx')
  const operation = { current: '' }; let renderer; globalThis.IS_REACT_ACT_ENVIRONMENT = true
  function Harness() {
    const [state, setState] = useState({ transcript: [], draft: 'Connect Drive', note: '', busy: false, pending: null, action: null })
    const id = useRef(0)
    return React.createElement(module.Assistant, { workspaceId: 'workspace-1', workspaceRevision: 4,
      enabled: true, readOnly: false, state, setState, nextId: () => ++id.current, operationRef: operation })
  }
  const priorConsoleError = console.error; console.error = () => {}
  try {
    await act(async () => { renderer = TestRenderer.create(React.createElement(Harness)) })
    const form = () => renderer.root.findByProps({ className: 'composer' })
    const input = () => renderer.root.findByProps({ id: 'cordia-message' })
    await act(async () => { form().props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    await act(async () => { input().props.onChange({ target: { value: '  Connect Drive  ' } }) })
    await act(async () => { form().props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    await act(async () => { input().props.onChange({ target: { value: 'Connect Drive' } }) })
    await act(async () => { form().props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    await act(async () => { input().props.onChange({ target: { value: 'Connect GitHub' } }) })
    await act(async () => { form().props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    assert.equal(requests.length, 4)
    assert.equal(requests[0].idempotency_key, requests[1].idempotency_key)
    assert.equal(requests[1].idempotency_key, requests[2].idempotency_key)
    assert.notEqual(requests[2].idempotency_key, requests[3].idempotency_key)
  } finally {
    if (renderer) await act(async () => { renderer.unmount() })
    console.error = priorConsoleError; Date.now = originalNow; await vite.close()
    for (const [name, descriptor] of originals) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor)
      else delete globalThis[name]
    }
  }
})

test('rendered production Assistant submits one revisioned turn and refreshes once after a proposal', async () => {
  const originals = new Map()
  const replace = (name, value) => {
    originals.set(name, Object.getOwnPropertyDescriptor(globalThis, name))
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value })
  }
  replace('location', { hostname: 'cordia.example.test' })
  replace('localStorage', { getItem: () => null })
  replace('document', { activeElement: null })
  const requests = []
  replace('fetch', async (_url, options) => {
    requests.push(options)
    return { ok: true, status: 200, json: async () => ({
      ok: true, speech: 'I prepared a connector setup card.', revision: 5,
      action: { kind: 'propose_connector', state: 'setup_required',
        connector_id: 'issue_tracker', setup_kind: 'api_key' },
    }) }
  })
  const vite = await createServer({ configFile: false, server: { middlewareMode: true } })
  const module = await vite.ssrLoadModule('/src/WorkspaceView.jsx')
  let refreshes = 0
  const operation = { current: '' }
  function Harness() {
    const [state, setState] = useState({
      transcript: [], draft: 'Connect my issue tracker', note: '', busy: false, pending: null, action: null,
    })
    const id = useRef(0)
    return React.createElement(module.Assistant, {
      workspaceId: 'workspace-1', workspaceRevision: 4, hasMemory: true, hasStoredTurns: false,
      enabled: true, readOnly: false, state, setState, nextId: () => ++id.current,
      operationRef: operation, refresh: async () => { refreshes += 1 },
    })
  }
  const originalConsoleError = console.error
  console.error = () => {}
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  let renderer
  try {
    await act(async () => { renderer = TestRenderer.create(React.createElement(Harness)) })
    renderer.root.findByProps({ 'aria-label': 'Send message to Cordia' })
    const form = renderer.root.findByProps({ className: 'composer' })
    await act(async () => { form.props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    assert.equal(requests.length, 1)
    const payload = JSON.parse(requests[0].body)
    assert.deepEqual(Object.keys(payload).sort(), ['id', 'idempotency_key', 'message', 'revision'])
    assert.deepEqual({ id: payload.id, revision: payload.revision, message: payload.message }, {
      id: 'workspace-1', revision: 4, message: 'Connect my issue tracker',
    })
    assert.match(payload.idempotency_key, /^turn-[a-z0-9]+-1$/)
    assert.equal(refreshes, 1)
    renderer.root.findByProps({ className: 'assistant-action-card' })
    const rendered = JSON.stringify(renderer.toJSON())
    assert.equal(rendered.includes('Set up issue tracker'), true)
    assert.equal(rendered.includes('Setup is required before this connector is available.'), true)
  } finally {
    if (renderer) await act(async () => { renderer.unmount() })
    console.error = originalConsoleError
    await vite.close()
    for (const [name, descriptor] of originals) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor)
      else delete globalThis[name]
    }
  }
})

test('rendered Assistant retries an ambiguous committed proposal with the same idempotency key', async () => {
  const originals = new Map()
  for (const [name, value] of Object.entries({ location: { hostname: 'cordia.example.test' },
    localStorage: { getItem: () => null }, document: { activeElement: null } })) {
    originals.set(name, Object.getOwnPropertyDescriptor(globalThis, name))
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value })
  }
  const requests = []; let refreshes = 0
  Object.defineProperty(globalThis, 'fetch', { configurable: true, writable: true, value: async (_url, options) => {
    requests.push(JSON.parse(options.body))
    if (requests.length === 1) throw new Error('lost response after commit')
    return { ok: true, status: 200, json: async () => ({ ok: true, speech: 'I prepared a connector setup card.', revision: 5,
      action: { kind: 'propose_connector', state: 'setup_required', connector_id: 'issue_tracker', setup_kind: 'api_key' } }) }
  } })
  const vite = await createServer({ configFile: false, server: { middlewareMode: true } })
  const module = await vite.ssrLoadModule('/src/WorkspaceView.jsx')
  const operation = { current: '' }; let renderer; globalThis.IS_REACT_ACT_ENVIRONMENT = true
  function Harness() {
    const [state, setState] = useState({ transcript: [], draft: 'Connect my issue tracker', note: '', busy: false, pending: null, action: null })
    const id = useRef(0)
    return React.createElement(module.Assistant, { workspaceId: 'workspace-1', workspaceRevision: 4,
      enabled: true, readOnly: false, state, setState, nextId: () => ++id.current, operationRef: operation,
      refresh: async () => { refreshes += 1 } })
  }
  const priorConsoleError = console.error; console.error = () => {}
  try {
    await act(async () => { renderer = TestRenderer.create(React.createElement(Harness)) })
    const form = () => renderer.root.findByProps({ className: 'composer' })
    await act(async () => { form().props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    await act(async () => { form().props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    assert.equal(requests.length, 2)
    assert.equal(requests[0].idempotency_key, requests[1].idempotency_key)
    assert.equal(refreshes, 1)
    assert.equal(renderer.root.findAllByProps({ className: 'assistant-action-card' }).length, 1)
  } finally {
    if (renderer) await act(async () => { renderer.unmount() })
    console.error = priorConsoleError; await vite.close()
    for (const [name, descriptor] of originals) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor)
      else delete globalThis[name]
    }
  }
})

test('rendered Assistant retries a malformed successful response with the same idempotency key', async () => {
  const originals = new Map()
  for (const [name, value] of Object.entries({ location: { hostname: 'cordia.example.test' },
    localStorage: { getItem: () => null }, document: { activeElement: null } })) {
    originals.set(name, Object.getOwnPropertyDescriptor(globalThis, name))
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value })
  }
  const requests = []; let refreshes = 0
  Object.defineProperty(globalThis, 'fetch', { configurable: true, writable: true, value: async (_url, options) => {
    requests.push(JSON.parse(options.body))
    const body = requests.length === 1
      ? { ok: true, speech: 'Committed but malformed.', revision: 5, action: {} }
      : { ok: true, speech: 'I prepared a connector setup card.', revision: 5,
          action: { kind: 'propose_connector', state: 'setup_required', connector_id: 'issue_tracker', setup_kind: 'api_key' } }
    return { ok: true, status: 200, json: async () => body }
  } })
  const vite = await createServer({ configFile: false, server: { middlewareMode: true } })
  const module = await vite.ssrLoadModule('/src/WorkspaceView.jsx')
  const operation = { current: '' }; let renderer; globalThis.IS_REACT_ACT_ENVIRONMENT = true
  function Harness() {
    const [state, setState] = useState({ transcript: [], draft: 'Connect my issue tracker', note: '', busy: false, pending: null, action: null })
    const id = useRef(0)
    return React.createElement(module.Assistant, { workspaceId: 'workspace-1', workspaceRevision: 4,
      enabled: true, readOnly: false, state, setState, nextId: () => ++id.current, operationRef: operation,
      refresh: async () => { refreshes += 1 } })
  }
  const priorConsoleError = console.error; console.error = () => {}
  try {
    await act(async () => { renderer = TestRenderer.create(React.createElement(Harness)) })
    const form = () => renderer.root.findByProps({ className: 'composer' })
    await act(async () => { form().props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    await act(async () => { form().props.onSubmit({ preventDefault() {} }) })
    await new Promise((resolve) => setTimeout(resolve, 0))
    assert.equal(requests.length, 2)
    assert.equal(requests[0].idempotency_key, requests[1].idempotency_key)
    assert.equal(refreshes, 1)
    assert.equal(renderer.root.findAllByProps({ className: 'assistant-action-card' }).length, 1)
  } finally {
    if (renderer) await act(async () => { renderer.unmount() })
    console.error = priorConsoleError; await vite.close()
    for (const [name, descriptor] of originals) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor)
      else delete globalThis[name]
    }
  }
})
