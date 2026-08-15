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
