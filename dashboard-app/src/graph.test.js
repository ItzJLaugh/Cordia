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
