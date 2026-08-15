import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

import { alidoraMapToFlow } from './graph.js'

const connectorFixture = JSON.parse(fs.readFileSync(
  new URL('../../backend/tests/fixtures/alidora_connector_display.json', import.meta.url),
  'utf8',
))

test('alidoraMapToFlow consumes the backend connector display contract', () => {
  const flow = alidoraMapToFlow(connectorFixture.expected_map)
  const byId = new Map(flow.nodes.map((node) => [node.id, node]))

  assert.deepEqual(byId.get('connector:github').data.connectorStatus, {
    consent: 'confirmed',
    implementation: 'live',
    lifecycle: 'live',
    runtime: 'live',
  })
  assert.deepEqual(byId.get('connector:notion').data.connectorStatus, {
    consent: 'suggested',
    implementation: 'planned',
    lifecycle: 'proposed',
    runtime: 'not_observed',
  })
  assert.equal(JSON.stringify(flow).includes('credential=synthetic-stripe-example'), false)
})

test('alidoraMapToFlow drops connector nodes with invalid display enums', () => {
  const flow = alidoraMapToFlow({
    nodes: [{
      id: 'connector:github',
      kind: 'connector',
      label: 'GitHub',
      detail: '',
      connector_status: {
        consent: 'authorized',
        implementation: 'live',
        lifecycle: 'live',
        runtime: 'live',
      },
    }],
    edges: [],
  })

  assert.deepEqual(flow.nodes, [])
})

test('alidoraMapToFlow sorts safe nodes and emits a non-editable graph', () => {
  const flow = alidoraMapToFlow({
    nodes: [
      {
        id: 'skill:deploy', kind: 'skill', label: 'Deploy', detail: 'Release',
        status: 'invented-outside-the-contract', secret: 'must-not-cross-the-renderer-boundary',
      },
      { id: 'agent:review', kind: 'agent', label: 'Review', detail: '' },
    ],
    edges: [
      { from: 'agent:review', to: 'skill:deploy', hidden: 'must-not-be-copied' },
      { from: 'agent:review', to: 'agent:missing' },
    ],
  })

  assert.deepEqual(flow.nodes.map((node) => node.id), ['agent:review', 'skill:deploy'])
  assert.deepEqual(flow.nodes[1].data, {
    kind: 'skill', label: 'Deploy', detail: 'Release',
  })
  assert.equal(flow.nodes[0].draggable, false)
  assert.equal(flow.nodes[0].connectable, false)
  assert.equal(flow.nodes[0].deletable, false)
  assert.deepEqual(flow.edges.map(({ source, target }) => ({ source, target })), [
    { source: 'agent:review', target: 'skill:deploy' },
  ])
})

test('alidoraMapToFlow drops unsafe node identity and strips secret or path-shaped display text', () => {
  const flow = alidoraMapToFlow({
    nodes: [
      { id: 'C:\\private\\agent', kind: 'agent', label: 'Unsafe id', detail: '' },
      { id: 'agent:wrong-kind', kind: 'runtime_secret', label: 'Unsafe kind', detail: '' },
      { id: 'agent:review', kind: 'agent', label: 'password=hunter2', detail: 'Checks evidence.' },
      { id: 'skill:deploy', kind: 'skill', label: 'Deploy', detail: 'Open C:\\private\\workspace' },
      {
        id: 'connector:github', kind: 'connector', label: 'token=private-value', detail: '',
        connector_status: { consent: 'confirmed', implementation: 'live', lifecycle: 'live', runtime: 'live' },
      },
    ],
    edges: [
      { from: 'C:\\private\\agent', to: 'skill:deploy' },
      { from: 'agent:review', to: 'skill:deploy' },
      { from: 'agent:wrong-kind', to: 'skill:deploy' },
    ],
  })

  assert.deepEqual(flow.nodes.map((node) => node.id), ['agent:review', 'connector:github', 'skill:deploy'])
  assert.deepEqual(flow.nodes.map((node) => node.data), [
    { kind: 'agent', label: '', detail: 'Checks evidence.' },
    {
      kind: 'connector', label: '', detail: '',
      connectorStatus: { consent: 'confirmed', implementation: 'live', lifecycle: 'live', runtime: 'live' },
    },
    { kind: 'skill', label: 'Deploy', detail: '' },
  ])
  assert.deepEqual(flow.edges.map(({ source, target }) => ({ source, target })), [
    { source: 'agent:review', target: 'skill:deploy' },
  ])
  assert.equal(JSON.stringify(flow).includes('private'), false)
  assert.equal(JSON.stringify(flow).includes('hunter2'), false)
  assert.equal(JSON.stringify(flow).includes('runtime_secret'), false)
})

test('alidoraMapToFlow strips metadata-prefixed local paths from node text', () => {
  const localPaths = [
    'path:C:\\private\\workspace',
    'path:C:private',
    'path:/home/cordia/private',
    'file:///home/cordia/private',
    'path:\\\\server\\private',
  ]

  for (const value of localPaths) {
    const flow = alidoraMapToFlow({
      nodes: [{ id: 'agent:review', kind: 'agent', label: value, detail: value }],
      edges: [],
    })
    assert.deepEqual(flow.nodes[0].data, { kind: 'agent', label: '', detail: '' }, value)
  }
})

test('alidoraMapToFlow rejects token-shaped and drive-relative node and edge identifiers', () => {
  const flow = alidoraMapToFlow({
    nodes: [
      { id: 'agent:1', kind: 'agent', label: 'Agent 1', detail: '' },
      { id: 'skill:1', kind: 'skill', label: 'Skill 1', detail: '' },
      { id: 'ghp_abcdefghijk', kind: 'agent', label: 'Credential id', detail: '' },
      { id: 'C:private', kind: 'skill', label: 'Drive-relative id', detail: '' },
    ],
    edges: [
      { from: 'agent:1', to: 'skill:1' },
      { from: 'ghp_abcdefghijk', to: 'skill:1' },
      { from: 'agent:1', to: 'C:private' },
    ],
  })

  assert.deepEqual(flow.nodes.map((node) => node.id), ['agent:1', 'skill:1'])
  assert.deepEqual(flow.edges.map(({ source, target }) => ({ source, target })), [
    { source: 'agent:1', target: 'skill:1' },
  ])
  assert.equal(JSON.stringify(flow).includes('ghp_'), false)
  assert.equal(JSON.stringify(flow).includes('C:private'), false)
})

test('alidoraMapToFlow preserves bounded synthetic entity ids without admitting workspace ids or credential prefixes', () => {
  const flow = alidoraMapToFlow({
    nodes: [
      { id: 'agent:review', kind: 'agent', label: 'Reviewer', detail: '' },
      { id: 'skill:summarize', kind: 'skill', label: 'Summarize', detail: '' },
      {
        id: 'connector:github', kind: 'connector', label: 'GitHub', detail: '',
        connector_status: { consent: 'confirmed', implementation: 'live', lifecycle: 'live', runtime: 'live' },
      },
      { id: 'ghp_testvalue', kind: 'agent', label: 'Unsafe', detail: '' },
      { id: 'AKIA1234567890ABCDEF', kind: 'skill', label: 'Unsafe', detail: '' },
      { id: 'workspace-1', kind: 'agent', label: 'Wrong boundary', detail: '' },
    ],
    edges: [
      { from: 'agent:review', to: 'skill:summarize' },
      { from: 'workspace-1', to: 'skill:summarize' },
    ],
  })

  assert.deepEqual(flow.nodes.map((node) => node.id), [
    'agent:review', 'connector:github', 'skill:summarize',
  ])
  assert.deepEqual(flow.edges.map(({ source, target }) => ({ source, target })), [
    { source: 'agent:review', target: 'skill:summarize' },
  ])
})

test('getApi bounds secret-bearing transport failures', async () => {
  const originals = new Map()
  function replaceGlobal(name, value) {
    originals.set(name, Object.getOwnPropertyDescriptor(globalThis, name))
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value })
  }

  replaceGlobal('location', { hostname: 'alidora.example.test' })
  replaceGlobal('localStorage', { getItem: () => null })
  replaceGlobal('fetch', async () => {
    throw new Error('connection failed at C:\\private\\workspace with token=secret-value')
  })

  try {
    const { getApi } = await import('./api.js?transport-regression')
    await assert.rejects(
      getApi('/surveyor/alidora/map?id=w-1'),
      (error) => error.message === 'Request failed',
    )
  } finally {
    for (const [name, descriptor] of originals) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor)
      else delete globalThis[name]
    }
  }
})

test('getApi never exposes safe-looking transport failures', async () => {
  const originals = new Map()
  function replaceGlobal(name, value) {
    originals.set(name, Object.getOwnPropertyDescriptor(globalThis, name))
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value })
  }

  replaceGlobal('location', { hostname: 'alidora.example.test' })
  replaceGlobal('localStorage', { getItem: () => null })
  replaceGlobal('fetch', async () => Promise.reject(new Error('offline temporarily')))

  try {
    const { getApi } = await import('./api.js?friendly-transport-regression')
    await assert.rejects(
      getApi('/surveyor/alidora/map?id=w-1'),
      (error) => error.message === 'Request failed',
    )
  } finally {
    for (const [name, descriptor] of originals) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor)
      else delete globalThis[name]
    }
  }
})
