import assert from 'node:assert/strict'
import test from 'node:test'

import {
  assistantReplyModel,
  assistantTurnFailed,
  assistantTurnStarted,
  isAssistantSendKey,
  routeFromSearch,
  workspaceRendererModel,
} from '../src/workspace-view.js'

const workspaceResponse = {
  ok: true,
  workspace: {
    id: 'workspace-1',
    title: 'Launch workspace',
    description: 'Coordinate the evidence review.',
    windows: [
      { id: 'notes', kind: 'derived', title: 'Evidence notes' },
      { id: 'agent-reviewer', kind: 'agent', title: 'Review agent' },
      { id: 'github-repositories', kind: 'connector', connector_id: 'github', title: 'GitHub repositories' },
    ],
    agents: [{ id: 'reviewer', name: 'Reviewer', description: 'Checks the evidence.' }],
    workflow: { steps: [{ id: 'review', agentId: 'reviewer', toolIds: ['summarize'], requiresApproval: true }] },
    connectors: [{
      id: 'github', status: 'confirmed', implementation_status: 'live', lifecycle: 'live', runtime_status: 'live',
    }],
    context_sources: [
      { kind: 'artifact', ref: 'runtime/fde-tasks.md' },
      { kind: 'github_repository', id: 'CordiaHQ/product', label: 'CordiaHQ/product' },
    ],
    secret: 'workspace-secret-must-not-render',
  },
}

const supplemental = {
  artifacts: {
    ok: true,
    artifacts: {
      'runtime/fde-tasks.md': '# FDE Mission Brief\nVerify the launch evidence.',
      'source/private.md': 'private artifact body must not render',
    },
    connector_catalog: { github: { token: 'catalog-secret-must-not-render' } },
  },
  approvals: {
    ok: true,
    approvals: [{ id: 'approval-1', summary: 'Publish the report?', status: 'pending', run_id: 'private-run' }],
  },
  capabilities: {
    ok: true,
    capabilities: [{
      name: 'github.read_repositories', summary: 'Read repository metadata.', decision: 'ALLOW',
      connector: 'github', reason: 'internal policy explanation must not render',
    }],
  },
  skills: {
    ok: true,
    skills: [{
      id: 'github_repository_review', name: 'Review repositories', summary: 'Collect repository metadata.',
      permission: 'ALLOW', available: true, required_capabilities: ['private-capability-shape'],
    }],
  },
  activity: {
    ok: true,
    activity: [{ event_type: 'interface_run', created: '2026-08-14T10:00:00Z', payload: { prompt: 'private prompt' } }],
  },
}

test('routeFromSearch keeps a valid workspace id and defaults every non-Alidora view to Workspace', () => {
  assert.deepEqual(routeFromSearch('?workspace=workspace-1'), {
    phase: 'ready', workspaceId: 'workspace-1', view: 'workspace',
    workspaceHref: '?workspace=workspace-1', alidoraHref: '?workspace=workspace-1&view=alidora',
  })
  assert.equal(routeFromSearch('?workspace=workspace-1&view=live').view, 'workspace')
  assert.equal(routeFromSearch('?workspace=workspace-1&view=alidora').view, 'alidora')
})

test('routeFromSearch fails closed for missing or path-shaped workspace ids', () => {
  assert.deepEqual(routeFromSearch(''), {
    phase: 'missing', workspaceId: '', view: 'workspace', workspaceHref: '', alidoraHref: '',
  })
  assert.equal(routeFromSearch('?workspace=C%3A%5Cprivate%5Cworkspace').phase, 'missing')
  assert.equal(routeFromSearch('?workspace=token%3Asecret-value').phase, 'missing')
})

test('workspaceRendererModel emits only allow-listed artifact models in stable category order', () => {
  const model = workspaceRendererModel(workspaceResponse, supplemental, 'workspace-1')

  assert.deepEqual({ title: model.title, description: model.description }, {
    title: 'Launch workspace', description: 'Coordinate the evidence review.',
  })
  assert.deepEqual(model.cards.map(({ id, kind, title }) => ({ id, kind, title })), [
    { id: 'mission', kind: 'mission', title: 'Cordia mission' },
    { id: 'context', kind: 'context', title: 'Active context' },
    { id: 'workflow', kind: 'workflow', title: 'Workflow' },
    { id: 'agent:reviewer', kind: 'agent', title: 'Reviewer' },
    { id: 'connector:github', kind: 'connector', title: 'github' },
    { id: 'derived:notes', kind: 'derived-note', title: 'Evidence notes' },
    { id: 'skill:github_repository_review', kind: 'skill', title: 'Review repositories' },
    { id: 'capability:github.read_repositories', kind: 'capability', title: 'Read repository metadata.' },
    { id: 'approval:approval-1', kind: 'approval', title: 'Approval needed' },
    { id: 'activity:0000', kind: 'activity', title: 'Recent activity' },
  ])
  assert.deepEqual(model.cards[0].body, 'Verify the launch evidence.')
  assert.deepEqual(model.cards[1].items, [{ label: 'CordiaHQ/product', meta: 'GitHub repository' }])
  assert.deepEqual(model.cards[2].items, [{ label: 'reviewer', meta: 'summarize · approval required' }])
  assert.deepEqual(model.cards[4].items, [
    { label: 'Consent', meta: 'confirmed' },
    { label: 'Adapter', meta: 'live' },
    { label: 'Lifecycle', meta: 'live' },
    { label: 'Runtime', meta: 'live' },
  ])
  assert.deepEqual(model.cards[6].badge, 'Available now')
  assert.deepEqual(model.cards[7].badge, 'Can use')
  assert.equal(JSON.stringify(model).includes('private'), false)
  assert.equal(JSON.stringify(model).includes('secret'), false)
  assert.equal(JSON.stringify(model).includes('prompt'), false)
})

test('workspaceRendererModel rejects malformed and cross-workspace canonical responses', () => {
  assert.equal(workspaceRendererModel({ ok: true, workspace: [] }, supplemental, 'workspace-1'), null)
  assert.equal(workspaceRendererModel(workspaceResponse, supplemental, 'workspace-2'), null)
})

test('workspaceRendererModel ignores malformed supplemental categories and unsafe mission text', () => {
  const unsafe = structuredClone(supplemental)
  unsafe.artifacts.artifacts['runtime/fde-tasks.md'] = '# FDE Mission Brief\nOpen C:\\private\\workspace with token=secret'
  unsafe.approvals.approvals = { arbitrary: true }
  unsafe.capabilities.capabilities[0].decision = 'EXECUTE'
  unsafe.skills.skills[0].id = 'token:secret'
  unsafe.activity.activity[0].event_type = 'C:\\private\\event'

  const model = workspaceRendererModel(workspaceResponse, unsafe, 'workspace-1')
  assert.equal(model.cards.some((card) => card.kind === 'mission'), false)
  assert.equal(model.cards.some((card) => card.kind === 'approval'), false)
  assert.equal(model.cards.some((card) => card.kind === 'capability'), false)
  assert.equal(model.cards.some((card) => card.kind === 'skill'), false)
  assert.equal(model.cards.some((card) => card.kind === 'activity'), false)
})

test('assistant turn helpers withdraw failed optimistic messages and restore the bounded draft', () => {
  const started = assistantTurnStarted({ transcript: [], draft: '  Review this  ', note: '' }, 7)
  assert.deepEqual(started, {
    transcript: [{ id: 7, who: 'you', text: 'Review this' }],
    draft: '', note: '', busy: true, pending: { id: 7, text: 'Review this' },
  })

  assert.deepEqual(assistantTurnFailed(started, 'The server is unreachable right now.'), {
    transcript: [], draft: 'Review this', note: 'The server is unreachable right now.', busy: false, pending: null,
  })
})

test('assistant Enter handling sends only outside IME composition and without Shift', () => {
  assert.equal(isAssistantSendKey({ key: 'Enter', shiftKey: false, nativeEvent: { isComposing: false, keyCode: 13 } }), true)
  assert.equal(isAssistantSendKey({ key: 'Enter', shiftKey: true, nativeEvent: { isComposing: false, keyCode: 13 } }), false)
  assert.equal(isAssistantSendKey({ key: 'Enter', shiftKey: false, nativeEvent: { isComposing: true, keyCode: 13 } }), false)
  assert.equal(isAssistantSendKey({ key: 'Enter', shiftKey: false, nativeEvent: { isComposing: false, keyCode: 229 } }), false)
})

test('assistantReplyModel allow-lists bounded output and truthful limited-mode note', () => {
  assert.deepEqual(assistantReplyModel({
    ok: true,
    output: 'The evidence review is ready.',
    llm: { live: false, note: 'Local fallback is active.', mode: 'private-internal-mode' },
    approval: { summary: 'private approval body' },
  }), {
    text: 'The evidence review is ready.',
    limited: true,
    note: 'Local fallback is active.',
  })
  assert.equal(assistantReplyModel({ ok: true, output: 'Open C:\\private\\workspace with token=secret' }), null)
  assert.equal(assistantReplyModel({ ok: true, output: { arbitrary: true } }), null)
})

test('assistantReplyModel preserves ordinary Unicode punctuation as inert text', () => {
  assert.deepEqual(assistantReplyModel({
    ok: true,
    output: 'Here’s the review — it’s ready.',
    llm: { live: false, note: 'Fallback model — current results may be limited.' },
  }), {
    text: 'Here’s the review — it’s ready.',
    limited: true,
    note: 'Fallback model — current results may be limited.',
  })
})
