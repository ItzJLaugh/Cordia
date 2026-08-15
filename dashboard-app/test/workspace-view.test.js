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
  assert.equal(routeFromSearch('?workspace=C%3Adrive-relative').phase, 'missing')
  assert.equal(routeFromSearch('?workspace=token%3Asecret-value').phase, 'missing')

  for (const credentialId of [
    'sk-abcdefghijk',
    'ghp_abcdefghijklmnopqrstuvwxyz',
    'github_pat_abcdefghijklmnopqrstuvwxyz0123456789',
    'AKIA1234567890ABCDEF',
    'token.secret-value',
  ]) {
    const route = routeFromSearch(`?workspace=${encodeURIComponent(credentialId)}`)
    assert.deepEqual(route, {
      phase: 'missing', workspaceId: '', view: 'workspace', workspaceHref: '', alidoraHref: '',
    }, credentialId)
  }
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
    { id: 'github-repository-surface', kind: 'github-repositories', title: 'GitHub repositories' },
    { id: 'derived:notes', kind: 'derived-note', title: 'Evidence notes' },
    { id: 'skill:github_repository_review', kind: 'skill', title: 'Review repositories' },
    { id: 'capability:github.read_repositories', kind: 'capability', title: 'Read repository metadata.' },
    { id: 'activity:0000', kind: 'activity', title: 'Recent account activity' },
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
  const cards = new Map(model.cards.map((card) => [card.id, card]))
  assert.deepEqual(cards.get('skill:github_repository_review').badge, 'Available now')
  assert.deepEqual(cards.get('capability:github.read_repositories').badge, 'Allowed by policy')
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

test('workspaceRendererModel labels the unscoped feed as Recent account activity', () => {
  const card = workspaceRendererModel(workspaceResponse, supplemental, 'workspace-1').cards
    .find((candidate) => candidate.kind === 'activity')
  assert.equal(card.title, 'Recent account activity')
})

test('workspaceRendererModel restores the declared GitHub repository artifact with one fixed same-origin route', () => {
  const model = workspaceRendererModel(workspaceResponse, supplemental, 'workspace-1')
  const card = model.cards.find((candidate) => candidate.id === 'github-repository-surface')

  assert.deepEqual(card, {
    id: 'github-repository-surface',
    kind: 'github-repositories',
    title: 'GitHub repositories',
    badge: 'Available now',
    body: 'GitHub is connected. Open the bounded repository view to review its available repositories.',
    link: { href: '/github.html', label: 'Open GitHub repositories' },
  })

  const withoutWindow = structuredClone(workspaceResponse)
  withoutWindow.workspace.windows = withoutWindow.workspace.windows
    .filter((window) => window.id !== 'github-repositories')
  assert.equal(workspaceRendererModel(withoutWindow, supplemental, 'workspace-1').cards
    .some((candidate) => candidate.kind === 'github-repositories'), false)
})

test('GitHub repository artifact reports setup-required, unavailable, and needs-attention truth', () => {
  const cases = [
    {
      label: 'empty canonical connector state',
      mutate(workspace) { workspace.connectors = [] },
      badge: 'Setup required',
      body: 'Connect GitHub before Cordia can read repositories in this bounded view.',
    },
    {
      label: 'planned adapter',
      mutate(workspace) { workspace.connectors[0].implementation_status = 'planned' },
      badge: 'Unavailable',
      body: 'GitHub repository access is not available on this surface yet.',
    },
    {
      label: 'unhealthy runtime',
      mutate(workspace) { workspace.connectors[0].runtime_status = 'needs_attention' },
      badge: 'Needs attention',
      body: 'GitHub needs attention before Cordia can read repositories.',
    },
  ]

  for (const scenario of cases) {
    const canonical = structuredClone(workspaceResponse)
    scenario.mutate(canonical.workspace)
    const card = workspaceRendererModel(canonical, supplemental, 'workspace-1').cards
      .find((candidate) => candidate.kind === 'github-repositories')
    assert.equal(card.badge, scenario.badge, scenario.label)
    assert.equal(card.body, scenario.body, scenario.label)
    assert.deepEqual(card.link, { href: '/github.html', label: 'Open GitHub repositories' }, scenario.label)
  }
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
  assert.equal(cards.get('capability:github.read_repositories').badge, 'Allowed by policy')
  assert.deepEqual(cards.get('capability:github.read_repositories').items, [
    { label: 'Connector readiness', meta: 'Available now' },
  ])
  assert.equal(cards.get('connector:desktop.local_repository').badge, 'Planned')
  assert.equal(cards.get('skill:local_git_status_wait').badge, 'Planned')
  assert.equal(cards.get('capability:desktop.git.status').badge, 'Allowed by policy')
  assert.deepEqual(cards.get('capability:desktop.git.status').items, [
    { label: 'Connector readiness', meta: 'Planned' },
  ])
  assert.equal(cards.get('skill:missing_connector_skill').badge, 'Unavailable')
  assert.equal(cards.get('capability:missing.read').badge, 'Allowed by policy')
  assert.deepEqual(cards.get('capability:missing.read').items, [
    { label: 'Connector readiness', meta: 'Missing' },
  ])
  assert.equal(cards.get('connector:unstable.connector').badge, 'Unavailable')
  assert.equal(cards.get('skill:unstable_connector_skill').badge, 'Unavailable')
  assert.equal(cards.get('capability:unstable.read').badge, 'Allowed by policy')
  assert.deepEqual(cards.get('capability:unstable.read').items, [
    { label: 'Connector readiness', meta: 'Needs attention' },
  ])
})

test('capability cards keep ASK and DENY authoritative across planned, missing, and unhealthy connectors', () => {
  const canonical = structuredClone(workspaceResponse)
  canonical.workspace.connectors.push(
    {
      id: 'planned.connector', status: 'confirmed', implementation_status: 'planned',
      lifecycle: 'needs_handoff', runtime_status: 'not_observed',
    },
    {
      id: 'unhealthy.connector', status: 'confirmed', implementation_status: 'live',
      lifecycle: 'failed', runtime_status: 'needs_attention',
    },
  )
  const feeds = structuredClone(supplemental)
  feeds.capabilities.capabilities = []
  const expected = new Map()
  for (const decision of ['ASK', 'DENY']) {
    for (const [readiness, connector] of [
      ['Planned', 'planned.connector'],
      ['Missing', 'missing.connector'],
      ['Needs attention', 'unhealthy.connector'],
    ]) {
      const suffix = readiness.toLowerCase().replace(' ', '_')
      const name = `${decision.toLowerCase()}.${suffix}`
      feeds.capabilities.capabilities.push({
        name,
        summary: `${decision} with ${readiness.toLowerCase()} connector.`,
        decision,
        connector,
        reason: 'internal policy detail must not render',
      })
      expected.set(`capability:${name}`, {
        badge: decision === 'ASK' ? 'Approval required' : 'Not allowed',
        items: [{ label: 'Connector readiness', meta: readiness }],
      })
    }
  }

  const cards = new Map(workspaceRendererModel(canonical, feeds, 'workspace-1').cards
    .filter((card) => card.kind === 'capability').map((card) => [card.id, card]))
  for (const [id, truth] of expected) {
    assert.equal(cards.get(id).badge, truth.badge, id)
    assert.deepEqual(cards.get(id).items, truth.items, id)
  }
  assert.equal(JSON.stringify([...cards.values()]).includes('internal policy detail'), false)
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
    {
      id: 'approval_planned_skill', name: 'Protected desktop publish', summary: 'Approval remains authoritative.',
      permission: 'ASK', available: false, required_connectors: ['desktop.local_repository'],
    },
    {
      id: 'denied_missing_skill', name: 'Denied missing publish', summary: 'Policy remains authoritative.',
      permission: 'DENY', available: false, required_connectors: ['missing.connector'],
    },
    {
      id: 'denied_unhealthy_skill', name: 'Denied unhealthy publish', summary: 'Policy remains authoritative.',
      permission: 'DENY', available: false, required_connectors: ['unstable.connector'],
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
  assert.equal(skills.get('skill:approval_planned_skill').action.reason,
    'Approval is required. This web view cannot continue the protected external action.')
  assert.equal(skills.get('skill:denied_missing_skill').action.reason, 'Cordia policy does not allow this skill.')
  assert.equal(skills.get('skill:denied_unhealthy_skill').action.reason, 'Cordia policy does not allow this skill.')
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

test('workspaceRendererModel applies the shared sensitive-text boundary to agents and supplemental cards', () => {
  const unsafeText = [
    'sk-testvalue',
    'ghp_testvalue',
    'github_pat_testvalue',
    'AKIA1234567890ABCDEF',
    'token: private',
    'password=private',
    'authorization.private',
    'credential.private',
    'C:private',
    'C:\\private\\workspace',
    '/home/cordia/private',
  ]

  for (const value of unsafeText) {
    const canonical = structuredClone(workspaceResponse)
    canonical.workspace.agents = [{ id: 'reviewer', name: value, description: value }]
    const feeds = structuredClone(supplemental)
    feeds.skills.skills[0].name = value
    feeds.capabilities.capabilities[0].summary = value
    feeds.activity.activity[0].event_type = value
    const model = workspaceRendererModel(canonical, feeds, 'workspace-1')
    assert.equal(JSON.stringify(model).includes(value), false, value)
    assert.equal(model.cards.some((card) => card.id === 'agent:reviewer'), false, value)
  }
})

test('workspaceRendererModel rejects metadata-prefixed local paths in bounded workspace fields', () => {
  const localPaths = [
    'path:C:\\private\\workspace',
    'path:C:private',
    'path:/home/cordia/private',
    'file:///home/cordia/private',
    'path:\\\\server\\private',
  ]
  const fields = [
    ['workspace title', (workspace, value) => { workspace.title = value }],
    ['workspace description', (workspace, value) => { workspace.description = value }],
    ['window title', (workspace, value) => { workspace.windows[0].title = value }],
    ['agent body', (workspace, value) => { workspace.agents[0].description = value }],
    ['workflow identifier', (workspace, value) => { workspace.workflow.steps[0].id = value }],
  ]

  for (const [field, update] of fields) {
    for (const value of localPaths) {
      const canonical = structuredClone(workspaceResponse)
      update(canonical.workspace, value)
      assert.equal(JSON.stringify(workspaceRendererModel(canonical, supplemental, 'workspace-1')).includes(value), false,
        `${field}: ${value}`)
    }
  }
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

test('loadWorkspaceTruth projects bounded rate-limited and partial supplemental-feed status', async () => {
  const scenarios = [
    {
      label: 'rate limited',
      failures: new Map([
        ['/surveyor/capabilities', 'rate-limit'],
        ['/surveyor/activity', 'offline'],
      ]),
      expectedStatus: {
        state: 'rate-limited',
        unavailable: ['capabilities', 'activity'],
      },
      expectedCard: {
        badge: 'Rate limited',
        body: 'Some supplemental workspace details are temporarily rate limited. Reload later to refresh the complete view.',
        items: [
          { label: 'Capabilities', meta: 'May be incomplete' },
          { label: 'Recent account activity', meta: 'May be incomplete' },
        ],
      },
    },
    {
      label: 'partial',
      failures: new Map([['/surveyor/skills', 'offline']]),
      expectedStatus: { state: 'partial', unavailable: ['skills'] },
      expectedCard: {
        badge: 'Partial view',
        body: 'Some supplemental workspace details could not be loaded. Reload to refresh the complete view.',
        items: [{ label: 'Skills', meta: 'May be incomplete' }],
      },
    },
  ]

  for (const scenario of scenarios) {
    const responses = new Map([
      ['/surveyor/workspace?id=workspace-1', workspaceResponse],
      ['/surveyor/artifacts', supplemental.artifacts],
      ['/surveyor/capabilities', supplemental.capabilities],
      ['/surveyor/skills', supplemental.skills],
      ['/surveyor/activity', supplemental.activity],
    ])
    const truth = await workspaceView.loadWorkspaceTruth(async (path) => {
      const kind = scenario.failures.get(path)
      if (kind) throw Object.assign(new Error(`authorization=private-${path}`), { kind })
      return responses.get(path)
    }, 'workspace-1', (error) => error.kind)

    assert.deepEqual(truth.supplemental.feedStatus, scenario.expectedStatus, scenario.label)
    const card = workspaceRendererModel(truth.workspace, truth.supplemental, 'workspace-1').cards
      .find((candidate) => candidate.id === 'supplemental-feed-status')
    assert.equal(card.badge, scenario.expectedCard.badge, scenario.label)
    assert.equal(card.body, scenario.expectedCard.body, scenario.label)
    assert.deepEqual(card.items, scenario.expectedCard.items, scenario.label)
    assert.equal(JSON.stringify(card).includes('authorization'), false, scenario.label)
    assert.equal(JSON.stringify(card).includes('/surveyor/'), false, scenario.label)
  }
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

test('assistantReplyModel projects only safe current-run pending approval status and pause copy', () => {
  const model = assistantReplyModel({
    ok: true,
    output: 'The customer message draft is ready.',
    llm: { live: true },
    approval: {
      id: 'approval_private_checkpoint',
      run_id: 'run_private',
      step_id: 'publish_private',
      status: 'pending',
      summary: 'Private customer message body.',
      payload: { authorization: 'Bearer private-value' },
    },
  })

  assert.deepEqual(model, {
    text: 'The customer message draft is ready.',
    limited: false,
    note: 'Cordia prepared a draft and paused for your approval. No protected continuation occurred.',
    approvalStatus: 'pending',
  })
  const rendered = JSON.stringify(model)
  for (const privateValue of [
    'approval_private_checkpoint', 'run_private', 'publish_private',
    'Private customer message body.', 'Bearer private-value',
  ]) assert.equal(rendered.includes(privateValue), false, privateValue)

  assert.deepEqual(assistantReplyModel({
    ok: true,
    output: 'The review is complete.',
    approval: { status: 'approved', id: 'must-not-render' },
  }), {
    text: 'The review is complete.', limited: false, note: '',
  })
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
