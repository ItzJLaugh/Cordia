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
