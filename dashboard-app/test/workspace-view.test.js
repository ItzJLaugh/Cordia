import assert from 'node:assert/strict'
import test from 'node:test'

import * as workspaceView from '../src/workspace-view.js'

const {
  assistantReplyModel,
  assistantTurnFailed,
  assistantTurnStarted,
  isAssistantSendKey,
  routeFromSearch,
  workspaceRendererModel,
} = workspaceView

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
      permission: 'ALLOW', available: true, required_connectors: ['github'],
      required_capabilities: ['private-capability-shape'],
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

  const storeId = '3b92e3b42cf94d96824322b7e33b07db'
  assert.deepEqual(routeFromSearch(`?workspace=${storeId}`), {
    phase: 'ready', workspaceId: storeId, view: 'workspace',
    workspaceHref: `?workspace=${storeId}`, alidoraHref: `?workspace=${storeId}&view=alidora`,
  })
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
  assert.equal(JSON.stringify(model).includes('Publish the report?'), false)
})

test('workspaceRendererModel never projects account-wide approvals into a workspace', () => {
  const model = workspaceRendererModel(workspaceResponse, {
    approvals: {
      ok: true,
      approvals: [{ id: 'approval-other-workspace', summary: 'Cross-workspace private decision', status: 'pending' }],
    },
  }, 'workspace-1')

  assert.equal(model.cards.some((card) => card.kind === 'approval'), false)
  assert.equal(JSON.stringify(model).includes('Cross-workspace private decision'), false)
})

test('workspaceRendererModel gates skill and capability badges on canonical connector readiness', () => {
  const canonical = structuredClone(workspaceResponse)
  canonical.workspace.connectors.push({
    id: 'desktop.local_repository', status: 'confirmed', implementation_status: 'planned',
    lifecycle: 'needs_handoff', runtime_status: 'not_observed',
  })
  canonical.workspace.connectors.push({
    id: 'unstable.connector', status: 'confirmed', implementation_status: 'live',
    lifecycle: 'failed', runtime_status: 'needs_attention',
  })
  const feeds = structuredClone(supplemental)
  feeds.skills.skills.push({
    id: 'local_git_status_wait', name: 'Check local Git status', summary: 'Inspect a selected repository.',
    permission: 'ALLOW', available: true, required_connectors: ['desktop.local_repository'],
  })
  feeds.skills.skills.push({
    id: 'missing_connector_skill', name: 'Missing connector skill', summary: 'Needs an unknown connector.',
    permission: 'ALLOW', available: true, required_connectors: ['missing.connector'],
  })
  feeds.skills.skills.push({
    id: 'unstable_connector_skill', name: 'Unstable connector skill', summary: 'Needs a healthy connector.',
    permission: 'ALLOW', available: true, required_connectors: ['unstable.connector'],
  })
  feeds.capabilities.capabilities.push({
    name: 'desktop.git.status', summary: 'Read local Git status.', decision: 'ALLOW',
    connector: 'desktop.local_repository',
  })
  feeds.capabilities.capabilities.push({
    name: 'missing.read', summary: 'Read a missing system.', decision: 'ALLOW', connector: 'missing.connector',
  })
  feeds.capabilities.capabilities.push({
    name: 'unstable.read', summary: 'Read an unstable system.', decision: 'ALLOW', connector: 'unstable.connector',
  })

  const cards = new Map(workspaceRendererModel(canonical, feeds, 'workspace-1').cards.map((card) => [card.id, card]))
  assert.equal(cards.get('skill:github_repository_review').badge, 'Available now')
  assert.equal(cards.get('capability:github.read_repositories').badge, 'Can use')
  assert.equal(cards.get('connector:desktop.local_repository').badge, 'Planned')
  assert.equal(cards.get('skill:local_git_status_wait').badge, 'Planned')
  assert.equal(cards.get('capability:desktop.git.status').badge, 'Planned')
  assert.equal(cards.get('skill:missing_connector_skill').badge, 'Unavailable')
  assert.equal(cards.get('capability:missing.read').badge, 'Unavailable')
  assert.equal(cards.get('connector:unstable.connector').badge, 'Unavailable')
  assert.equal(cards.get('skill:unstable_connector_skill').badge, 'Unavailable')
  assert.equal(cards.get('capability:unstable.read').badge, 'Unavailable')
})

test('workspaceRendererModel is the sole source of bounded skill action and gate truth', () => {
  const canonical = structuredClone(workspaceResponse)
  canonical.workspace.connectors.push(
    {
      id: 'desktop.local_repository', status: 'confirmed', implementation_status: 'planned',
      lifecycle: 'needs_handoff', runtime_status: 'not_observed',
    },
    {
      id: 'unstable.connector', status: 'confirmed', implementation_status: 'live',
      lifecycle: 'live', runtime_status: 'needs_attention',
    },
  )
  const feeds = structuredClone(supplemental)
  feeds.skills.skills.push(
    {
      id: 'temporarily_unavailable', name: 'Unavailable skill', summary: 'Unavailable at its capability boundary.',
      permission: 'ALLOW', available: false,
    },
    {
      id: 'approval_skill', name: 'Protected publish', summary: 'Requires a protected external continuation.',
      permission: 'ASK', available: false, required_connectors: ['github'],
    },
    {
      id: 'denied_skill', name: 'Denied publish', summary: 'Denied by Cordia policy.',
      permission: 'DENY', available: false, required_connectors: ['github'],
    },
    {
      id: 'missing_connector_skill', name: 'Missing connector skill', summary: 'Needs an unknown connector.',
      permission: 'ALLOW', available: true, required_connectors: ['missing.connector'],
    },
    {
      id: 'planned_connector_skill', name: 'Desktop Git status', summary: 'Runs only on the planned desktop surface.',
      permission: 'ALLOW', available: true, required_connectors: ['desktop.local_repository'],
    },
    {
      id: 'unhealthy_connector_skill', name: 'Unhealthy connector skill', summary: 'Needs a healthy connector.',
      permission: 'ALLOW', available: true, required_connectors: ['unstable.connector'],
    },
  )

  const skills = new Map(workspaceRendererModel(canonical, feeds, 'workspace-1').cards
    .filter((card) => card.kind === 'skill').map((card) => [card.id, card]))
  assert.deepEqual(skills.get('skill:github_repository_review').action, {
    kind: 'skill', id: 'github_repository_review',
    request: 'Run skill: Review repositories.', enabled: true, reason: '',
  })
  assert.deepEqual(skills.get('skill:temporarily_unavailable').action, {
    kind: 'skill', id: 'temporarily_unavailable', request: 'Run skill: Unavailable skill.',
    enabled: false, reason: 'This skill is not available through its declared capability.',
  })
  assert.equal(skills.get('skill:approval_skill').action.enabled, false)
  assert.equal(skills.get('skill:approval_skill').action.reason,
    'Approval is required. This web view cannot continue the protected external action.')
  assert.equal(skills.get('skill:denied_skill').action.reason, 'Cordia policy does not allow this skill.')
  assert.equal(skills.get('skill:missing_connector_skill').action.reason,
    'A required connector is not available in this workspace.')
  assert.equal(skills.get('skill:planned_connector_skill').action.reason,
    'This skill is planned for a desktop or local surface and is not available here.')
  assert.equal(skills.get('skill:unhealthy_connector_skill').action.reason,
    'A required connector needs attention before this skill can run.')
  assert.equal(JSON.stringify([...skills.values()]).includes('private-capability-shape'), false)
})

test('workspaceRendererModel retains connector-independent skills but rejects malformed connector prerequisites', () => {
  const feeds = structuredClone(supplemental)
  feeds.skills.skills = [
    {
      id: 'summarize_context', name: 'Summarize context', summary: 'Summarize the bounded workspace context.',
      permission: 'ALLOW', available: true,
    },
    {
      id: 'malformed_connectors', name: 'Malformed connectors', summary: 'Must not cross the renderer boundary.',
      permission: 'ALLOW', available: true, required_connectors: 'github',
    },
  ]

  const model = workspaceRendererModel(workspaceResponse, feeds, 'workspace-1')
  const skills = model.cards.filter((card) => card.kind === 'skill')
  assert.deepEqual(skills, [{
    id: 'skill:summarize_context', kind: 'skill', title: 'Summarize context',
    body: 'Summarize the bounded workspace context.', badge: 'Available now',
    action: {
      kind: 'skill', id: 'summarize_context', request: 'Run skill: Summarize context.',
      enabled: true, reason: '',
    },
  }])
  assert.equal(JSON.stringify(model).includes('Malformed connectors'), false)
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
  assert.equal(model.cards.some((card) => card.kind === 'capability'), false)
  assert.equal(model.cards.some((card) => card.kind === 'skill'), false)
  assert.equal(model.cards.some((card) => card.kind === 'activity'), false)
})

test('loadWorkspaceTruth refreshes canonical state and every bounded supplemental feed', async () => {
  assert.equal(typeof workspaceView.loadWorkspaceTruth, 'function')
  const requested = []
  const responses = new Map([
    ['/surveyor/workspace?id=workspace-1', workspaceResponse],
    ['/surveyor/artifacts', supplemental.artifacts],
    ['/surveyor/capabilities', supplemental.capabilities],
    ['/surveyor/skills', supplemental.skills],
    ['/surveyor/activity', supplemental.activity],
  ])
  const truth = await workspaceView.loadWorkspaceTruth(async (path) => {
    requested.push(path)
    return responses.get(path)
  }, 'workspace-1')

  assert.deepEqual(requested, [
    '/surveyor/workspace?id=workspace-1',
    '/surveyor/artifacts',
    '/surveyor/capabilities',
    '/surveyor/skills',
    '/surveyor/activity',
  ])
  assert.equal(truth.workspace, workspaceResponse)
  assert.deepEqual(Object.keys(truth.supplemental), ['artifacts', 'capabilities', 'skills', 'activity'])
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
