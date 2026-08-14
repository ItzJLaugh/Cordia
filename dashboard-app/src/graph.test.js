import assert from 'node:assert/strict'
import test from 'node:test'

import { alidoraMapToFlow } from './graph.js'

test('alidoraMapToFlow sorts safe nodes and emits a non-editable graph', () => {
  const flow = alidoraMapToFlow({
    nodes: [
      {
        id: 'skill:deploy', kind: 'skill', label: 'Deploy', detail: 'Release',
        status: 'ready', secret: 'must-not-cross-the-renderer-boundary',
      },
      { id: 'agent:review', kind: 'agent', label: 'Review', detail: '', status: 'ready' },
    ],
    edges: [
      { from: 'agent:review', to: 'skill:deploy', hidden: 'must-not-be-copied' },
      { from: 'agent:review', to: 'agent:missing' },
    ],
  })

  assert.deepEqual(flow.nodes.map((node) => node.id), ['agent:review', 'skill:deploy'])
  assert.deepEqual(flow.nodes[1].data, {
    kind: 'skill', label: 'Deploy', detail: 'Release', status: 'ready',
  })
  assert.equal(flow.nodes[0].draggable, false)
  assert.equal(flow.nodes[0].connectable, false)
  assert.equal(flow.nodes[0].deletable, false)
  assert.deepEqual(flow.edges.map(({ source, target }) => ({ source, target })), [
    { source: 'agent:review', target: 'skill:deploy' },
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
