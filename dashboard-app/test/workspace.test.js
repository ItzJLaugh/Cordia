import assert from 'node:assert/strict'
import test from 'node:test'

import { workspaceToRendererModel } from '../src/workspace.js'

const canonicalResponse = {
  ok: true,
  workspace: {
    id: 'workspace-1',
    windows: [
      {
        id: 'github-repositories',
        kind: 'connector',
        connector_id: 'github',
        title: 'GitHub repositories',
        view: 'repositories',
        secret: 'must-not-cross-the-renderer-boundary',
      },
      {
        id: 'research-notes',
        kind: 'derived',
        title: 'Research notes',
        view: 'live',
        live_view_supported: true,
        live_view_enabled: false,
        local_path: 'C:\\private\\workspace',
      },
    ],
    workflow: {
      steps: [
        { id: 'review', agentId: 'reviewer', toolIds: ['summarize'], requiresApproval: true },
        { id: 'research', agentId: 'researcher', toolIds: ['search'] },
      ],
    },
    connectors: [
      {
        id: 'notion', status: 'suggested', implementation_status: 'planned',
        lifecycle: 'proposed', runtime_status: 'not_observed', token: 'not-a-renderer-field',
      },
      {
        id: 'github', status: 'confirmed', implementation_status: 'live',
        lifecycle: 'live', runtime_status: 'live', authorization: 'Bearer private-value',
      },
    ],
    provenance: [{ source_path: 'C:\\private\\history' }],
  },
}

test('workspaceToRendererModel produces stable bounded cards, workflow rows, and connector truth', () => {
  const model = workspaceToRendererModel(canonicalResponse)

  assert.deepEqual(model.artifactCards, [
    {
      id: 'github-repositories',
      kind: 'connector',
      title: 'GitHub repositories',
      viewMode: { default: 'dash', liveAvailable: false },
      connector: {
        id: 'github',
        consent: 'confirmed',
        implementation: 'live',
        lifecycle: 'live',
        runtime: 'live',
      },
    },
    {
      id: 'research-notes',
      kind: 'derived',
      title: 'Research notes',
      viewMode: { default: 'dash', liveAvailable: false },
    },
  ])
  assert.deepEqual(model.workflowRows, [
    { id: 'research', agentId: 'researcher', skillIds: ['search'], requiresApproval: false },
    { id: 'review', agentId: 'reviewer', skillIds: ['summarize'], requiresApproval: true },
  ])
  assert.deepEqual(model.connectors, [
    {
      id: 'github', consent: 'confirmed', implementation: 'live', lifecycle: 'live', runtime: 'live',
    },
    {
      id: 'notion', consent: 'suggested', implementation: 'planned', lifecycle: 'proposed', runtime: 'not_observed',
    },
  ])
  assert.equal(JSON.stringify(model).includes('must-not-cross'), false)
  assert.equal(JSON.stringify(model).includes('private-value'), false)
  assert.equal(JSON.stringify(model).includes('C:\\private'), false)
})

test('workspaceToRendererModel is deterministic and opens LiveView only after support and user enablement', () => {
  const enabled = structuredClone(canonicalResponse)
  enabled.workspace.windows[1].live_view_enabled = true
  enabled.workspace.windows.reverse()
  enabled.workspace.workflow.steps.reverse()
  enabled.workspace.connectors.reverse()

  const model = workspaceToRendererModel(enabled)

  assert.deepEqual(model.artifactCards.map((card) => card.id), [
    'github-repositories',
    'research-notes',
  ])
  assert.deepEqual(model.workflowRows.map((row) => row.id), ['research', 'review'])
  assert.deepEqual(model.connectors.map((connector) => connector.id), ['github', 'notion'])
  assert.deepEqual(model.artifactCards[1].viewMode, { default: 'dash', liveAvailable: true })
})

test('workspaceToRendererModel fails closed for malformed input and unsafe fields', () => {
  assert.deepEqual(workspaceToRendererModel(null), {
    artifactCards: [], workflowRows: [], connectors: [], viewMode: { default: 'dash', liveAvailable: false },
  })
  assert.deepEqual(workspaceToRendererModel({ ok: true, workspace: {
    windows: [{ id: 'C:\\private\\card', kind: 'derived', title: 'token=secret' }],
    workflow: { steps: [{ id: '/private/step', agentId: 'agent', toolIds: ['tool'] }] },
    connectors: [{ id: 'github', status: 'confirmed', implementation_status: 'live', lifecycle: 'invalid', runtime_status: 'live' }],
  } }), {
    artifactCards: [], workflowRows: [], connectors: [], viewMode: { default: 'dash', liveAvailable: false },
  })
})

test('workspaceToRendererModel rejects credential-shaped identifiers from every renderer field', () => {
  const model = workspaceToRendererModel({ ok: true, workspace: {
    windows: [{ id: 'token:abc', kind: 'derived', title: 'Safe title' }],
    workflow: {
      steps: [{
        id: 'password:foo', agentId: 'authorization:BearerSecret', toolIds: ['token:abc'],
      }],
    },
    connectors: [{
      id: 'token:abc', status: 'confirmed', implementation_status: 'live', lifecycle: 'live', runtime_status: 'live',
    }],
  } })

  assert.deepEqual(model.artifactCards, [])
  assert.deepEqual(model.workflowRows, [])
  assert.deepEqual(model.connectors, [])
  assert.equal(JSON.stringify(model).includes('BearerSecret'), false)
})

test('workspaceToRendererModel applies one credential and path matrix to every canonical identifier', () => {
  const unsafeIds = [
    'sk-testvalue',
    'ghp_testvalue',
    'github_pat_testvalue',
    'AKIA1234567890ABCDEF',
    'token.private',
    'password.private',
    'authorization.private',
    'credential.private',
    'C:private',
    'C:\\private',
    'C:/private',
  ]
  const identifierFields = [
    ['window id', (workspace, value) => { workspace.windows[0].id = value }],
    ['window kind', (workspace, value) => { workspace.windows[0].kind = value }],
    ['window connector', (workspace, value) => { workspace.windows[0].connector_id = value }],
    ['workflow id', (workspace, value) => { workspace.workflow.steps[0].id = value }],
    ['workflow agent', (workspace, value) => { workspace.workflow.steps[0].agentId = value }],
    ['workflow tool', (workspace, value) => { workspace.workflow.steps[0].toolIds = [value] }],
    ['connector id', (workspace, value) => { workspace.connectors[0].id = value }],
  ]

  for (const [field, mutate] of identifierFields) {
    for (const value of unsafeIds) {
      const response = structuredClone(canonicalResponse)
      mutate(response.workspace, value)
      const rendered = JSON.stringify(workspaceToRendererModel(response))
      assert.equal(rendered.includes(value), false, `${field}: ${value}`)
    }
  }
})

test('workspaceToRendererModel drops secret-shaped window titles through the shared text boundary', () => {
  const unsafeTitles = [
    'sk-testvalue',
    'ghp_testvalue',
    'github_pat_testvalue',
    'AKIA1234567890ABCDEF',
    'token: private',
    'password=private',
    'authorization: Bearer private',
    'credential.private',
    'C:private',
    'C:\\private\\workspace',
    '/home/cordia/private',
  ]

  for (const title of unsafeTitles) {
    const response = structuredClone(canonicalResponse)
    response.workspace.windows[0].title = title
    const model = workspaceToRendererModel(response)
    assert.equal(model.artifactCards.some((card) => card.id === 'github-repositories'), false, title)
    assert.equal(JSON.stringify(model).includes(title), false, title)
  }
})

test('workspaceToRendererModel retains canonical connector truth when runtime has not been observed', () => {
  const model = workspaceToRendererModel({ ok: true, workspace: {
    windows: [{ id: 'github-repositories', kind: 'connector', connector_id: 'github', title: 'GitHub repositories' }],
    connectors: [{
      id: 'github', status: 'confirmed', implementation_status: 'live', lifecycle: 'needs_handoff',
    }],
  } })

  const expected = {
    id: 'github', consent: 'confirmed', implementation: 'live', lifecycle: 'needs_handoff', runtime: 'not_observed',
  }
  assert.deepEqual(model.connectors, [expected])
  assert.deepEqual(model.artifactCards[0].connector, expected)
})

test('workspaceToRendererModel keeps LiveView unavailable when support is false even if enabled', () => {
  const model = workspaceToRendererModel({ ok: true, workspace: {
    windows: [{
      id: 'research-notes', kind: 'derived', title: 'Research notes',
      live_view_supported: false, live_view_enabled: true,
    }],
  } })

  assert.deepEqual(model.artifactCards[0].viewMode, { default: 'dash', liveAvailable: false })
  assert.deepEqual(model.viewMode, { default: 'dash', liveAvailable: false })
})
