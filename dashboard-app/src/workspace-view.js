import { workspaceToRendererModel } from './workspace.js'
import { isSafeIdentifier, isSensitiveText } from './identifier.js'

const SAFE_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T[0-9:.+-]+Z?$/
const DECISIONS = new Set(['ALLOW', 'ASK', 'DENY'])
const PERMISSIONS = new Set(['ALLOW', 'ASK', 'DENY'])
const SUPPLEMENTAL_ENDPOINTS = {
  artifacts: '/surveyor/artifacts',
  capabilities: '/surveyor/capabilities',
  skills: '/surveyor/skills',
  activity: '/surveyor/activity',
}
const SUPPLEMENTAL_FEED_LABELS = {
  artifacts: 'Mission',
  capabilities: 'Capabilities',
  skills: 'Skills',
  activity: 'Recent account activity',
}
const GITHUB_REPOSITORIES_ENDPOINT = '/surveyor/github/repositories'
const INSPECTION_TABS = [
  { id: 'connected', label: 'Connected', kind: 'connector', empty: 'No connectors available' },
  { id: 'skills', label: 'Skills', kind: 'skill', empty: 'No skills available' },
  { id: 'access', label: 'Access', kind: 'capability', empty: 'No access decisions available' },
  { id: 'context', label: 'Context', kind: 'context', empty: 'No context available' },
  { id: 'automations', label: 'Automations', kind: '', empty: 'Automation details are unavailable' },
  { id: 'activity', label: 'Activity', kind: 'activity', empty: 'No recent account activity' },
]
const INSPECTION_FEEDS = {
  skills: {
    feed: 'skills',
    partial: 'Skill details are unavailable in this partial view',
    unavailable: 'Skill details are unavailable',
    'rate-limited': 'Skill details are temporarily rate limited',
  },
  access: {
    feed: 'capabilities',
    partial: 'Access details are unavailable in this partial view',
    unavailable: 'Access details are unavailable',
    'rate-limited': 'Access details are temporarily rate limited',
  },
  activity: {
    feed: 'activity',
    partial: 'Activity details are unavailable in this partial view',
    unavailable: 'Activity details are unavailable',
    'rate-limited': 'Activity details are temporarily rate limited',
  },
}

function safeId(value) {
  return isSafeIdentifier(value) ? value : ''
}

function safeText(value, limit = 160) {
  if (typeof value !== 'string') return ''
  const text = value.trim()
  if (!text || text.length > limit || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(text) || isSensitiveText(text)) return ''
  return text
}

function safeRepositoryLabel(source) {
  if (!source || typeof source !== 'object' || Array.isArray(source) || source.kind !== 'github_repository') return ''
  return safeRepositoryName(source.label) || safeRepositoryName(source.id)
}

function safeRepositoryName(value) {
  const name = typeof value === 'string' ? value.trim() : ''
  return /^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/.test(name) ? name : ''
}

function safeRepositoryDescription(value) {
  const description = safeText(value, 320)
  return description && !/[A-Za-z][A-Za-z0-9+.-]*:\/\//.test(description) ? description : ''
}

function safeRepositoryBranch(value) {
  const branch = safeText(value, 100)
  return /^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$/.test(branch) ? branch : ''
}

function listFrom(response, key) {
  return response && typeof response === 'object' && !Array.isArray(response)
    && response.ok === true && Array.isArray(response[key]) ? response[key] : []
}

function stable(records) {
  return records.sort((left, right) => left.id.localeCompare(right.id))
}

function connectorReadiness(connectors, requiredIds) {
  const byId = new Map(connectors.map((connector) => [connector.id, connector]))
  const required = requiredIds.map((id) => byId.get(id))
  if (required.some((connector) => !connector)) return 'missing'
  if (required.some((connector) => connector.implementation === 'planned')) return 'planned'
  if (required.some((connector) => connector.consent !== 'confirmed')) return 'connect'
  if (required.some((connector) => connector.lifecycle !== 'live' || connector.runtime !== 'live')) return 'unhealthy'
  return 'ready'
}

function shouldReadGithub(response, expectedWorkspaceId) {
  if (!response || typeof response !== 'object' || Array.isArray(response) || response.ok !== true
      || !response.workspace || typeof response.workspace !== 'object' || Array.isArray(response.workspace)
      || response.workspace.id !== expectedWorkspaceId) return false
  const model = workspaceToRendererModel(response)
  const declared = model.artifactCards.some((card) => (
    card.id === 'github-repositories' && card.kind === 'connector'
      && card.connector && card.connector.id === 'github'
  ))
  const connector = model.connectors.find((candidate) => candidate.id === 'github')
  return declared && connector && connector.consent === 'confirmed'
    && connector.implementation === 'live' && connector.runtime !== 'needs_attention'
}

function connectorIds(value) {
  if (value === undefined) return []
  if (!Array.isArray(value)) return null
  const ids = [...new Set(value.map(safeId).filter(Boolean))].sort((left, right) => left.localeCompare(right))
  return ids.length === value.length ? ids : null
}

function readinessBadge(readiness) {
  if (readiness === 'planned') return 'Planned'
  if (readiness === 'connect') return 'Connect first'
  if (readiness === 'missing' || readiness === 'unhealthy') return 'Unavailable'
  return ''
}

function readinessDetail(readiness) {
  if (readiness === 'ready') return 'Available now'
  if (readiness === 'planned') return 'Planned'
  if (readiness === 'connect') return 'Connect first'
  if (readiness === 'missing') return 'Missing'
  if (readiness === 'unhealthy') return 'Needs attention'
  return 'Unavailable'
}

function skillRequest(title) {
  const name = title.replace(/[.!?]+$/u, '').trim()
  return name ? safeText(`Run skill: ${name}.`, 200) : ''
}

function skillActionReason(skill, readiness) {
  if (skill.permission === 'DENY') return 'Cordia policy does not allow this skill.'
  if (skill.permission === 'ASK') return 'Approval is required. This web view cannot continue the protected external action.'
  if (readiness === 'missing') return 'A required connector is not available in this workspace.'
  if (readiness === 'planned') return 'This skill is planned for a desktop or local surface and is not available here.'
  if (readiness === 'connect') return 'Connect the required connector before running this skill.'
  if (readiness === 'unhealthy') return 'A required connector needs attention before this skill can run.'
  if (skill.available !== true) return 'This skill is not available through its declared capability.'
  return ''
}

function missionCard(response) {
  const artifacts = response && typeof response === 'object' && !Array.isArray(response)
    && response.ok === true && response.artifacts && typeof response.artifacts === 'object'
    && !Array.isArray(response.artifacts) ? response.artifacts : null
  if (!artifacts) return null
  const body = safeText(artifacts['runtime/fde-tasks.md'], 2000)
    .replace(/^# FDE Mission Brief\s*/i, '')
    .trim()
  return body ? { id: 'mission', kind: 'mission', title: 'Cordia mission', body } : null
}

function supplementalFeedStatus(status) {
  if (!status || typeof status !== 'object' || Array.isArray(status)
      || Object.keys(status).sort().join('|') !== 'state|unavailable'
      || !['partial', 'rate-limited'].includes(status.state)
      || !Array.isArray(status.unavailable) || status.unavailable.length < 1
      || status.unavailable.length > Object.keys(SUPPLEMENTAL_FEED_LABELS).length
      || new Set(status.unavailable).size !== status.unavailable.length
      || status.unavailable.some((feed) => !Object.hasOwn(SUPPLEMENTAL_FEED_LABELS, feed))) return null
  return { state: status.state, unavailable: [...status.unavailable] }
}

function supplementalFeedStatusCard(status) {
  const safeStatus = supplementalFeedStatus(status)
  if (!safeStatus) return null
  const unavailable = Object.keys(SUPPLEMENTAL_FEED_LABELS)
    .filter((feed) => safeStatus.unavailable.includes(feed))
  return {
    id: 'supplemental-feed-status',
    kind: 'status',
    title: 'Workspace details are incomplete',
    badge: safeStatus.state === 'rate-limited' ? 'Rate limited' : 'Partial view',
    body: safeStatus.state === 'rate-limited'
      ? 'Some supplemental workspace details are temporarily rate limited. Reload later to refresh the complete view.'
      : 'Some supplemental workspace details could not be loaded. Reload to refresh the complete view.',
    items: unavailable.map((feed) => ({
      label: SUPPLEMENTAL_FEED_LABELS[feed], meta: 'May be incomplete',
    })),
  }
}

function contextCard(workspace) {
  const items = (Array.isArray(workspace.context_sources) ? workspace.context_sources : [])
    .map((source) => {
      const label = safeRepositoryLabel(source)
      return label ? { label, meta: 'GitHub repository' } : null
    })
    .filter(Boolean)
    .sort((left, right) => left.label.localeCompare(right.label))
  return items.length ? { id: 'context', kind: 'context', title: 'Active context', items } : null
}

function contextProjection(workspace) {
  if (!Array.isArray(workspace.context_sources)) return { card: null, state: 'unavailable' }
  if (workspace.context_sources.length === 0) return { card: null, state: 'empty' }
  const card = contextCard(workspace)
  return { card, state: card ? 'available' : 'unavailable' }
}

function workflowCard(model) {
  const items = model.workflowRows.map((row) => ({
    label: row.agentId,
    meta: `${row.skillIds.length ? row.skillIds.join(', ') : 'No skills'}${row.requiresApproval ? ' · approval required' : ''}`,
  }))
  return items.length ? { id: 'workflow', kind: 'workflow', title: 'Workflow', items } : null
}

function agentCards(workspace) {
  const cards = (Array.isArray(workspace.agents) ? workspace.agents : []).map((agent) => {
    if (!agent || typeof agent !== 'object' || Array.isArray(agent)) return null
    const id = safeId(agent.id)
    const title = safeText(agent.name)
    if (!id || !title) return null
    const body = safeText(agent.description, 320)
    return { id: `agent:${id}`, kind: 'agent', title, ...(body ? { body } : {}) }
  }).filter(Boolean)
  return stable(cards)
}

function connectorCards(model) {
  return model.connectors.map((connector) => {
    const readiness = connectorReadiness(model.connectors, [connector.id])
    return {
      id: `connector:${connector.id}`,
      kind: 'connector',
      title: connector.id,
      badge: readiness === 'ready' ? 'Available now' : readinessBadge(readiness),
      items: [
        { label: 'Consent', meta: connector.consent },
        { label: 'Adapter', meta: connector.implementation },
        { label: 'Lifecycle', meta: connector.lifecycle.replaceAll('_', ' ') },
        { label: 'Runtime', meta: connector.runtime.replaceAll('_', ' ') },
      ],
    }
  })
}

function githubRepositorySummary(response) {
  if (!response || typeof response !== 'object' || Array.isArray(response) || response.ok !== true
      || response.capability !== 'github.read_repositories' || response.permission !== 'ALLOW'
      || !Number.isInteger(response.repository_limit) || response.repository_limit < 1
      || response.repository_limit > 30 || !Array.isArray(response.repositories)) return null

  const rows = response.repositories.map((repository) => {
    if (!repository || typeof repository !== 'object' || Array.isArray(repository)
        || typeof repository.private !== 'boolean') return null
    const label = safeRepositoryName(repository.name)
    if (!label) return null
    const branch = safeRepositoryBranch(repository.default_branch)
    const updated = typeof repository.updated_at === 'string' && SAFE_TIMESTAMP.test(repository.updated_at)
      ? repository.updated_at.slice(0, 10) : ''
    const detail = safeRepositoryDescription(repository.description)
    const meta = [repository.private ? 'Private' : 'Public', branch, updated ? `Updated ${updated}` : '']
      .filter(Boolean).join(' · ')
    return { label, meta, ...(detail ? { detail } : {}) }
  }).filter(Boolean)
    .sort((left, right) => JSON.stringify(left).localeCompare(JSON.stringify(right)))
  const unique = new Map()
  for (const row of rows) if (!unique.has(row.label)) unique.set(row.label, row)
  if (response.repositories.length > 0 && unique.size === 0) return null
  return {
    limit: response.repository_limit,
    items: [...unique.values()]
      .sort((left, right) => left.label.localeCompare(right.label))
      .slice(0, response.repository_limit),
  }
}

function githubReadFailed(response) {
  return response && typeof response === 'object' && !Array.isArray(response)
    && Object.keys(response).join('|') === 'state' && response.state === 'needs-attention'
}

function overlayGithubRuntime(model, response, attempted) {
  const connector = model.connectors.find((candidate) => candidate.id === 'github')
  if (!connector || connector.consent !== 'confirmed' || connector.implementation !== 'live') return model
  if (!attempted) return model

  const successful = githubRepositorySummary(response) !== null
  const github = {
    ...connector,
    lifecycle: successful ? 'live' : 'needs_handoff',
    runtime: successful ? 'live' : 'needs_attention',
  }
  return {
    ...model,
    connectors: model.connectors.map((candidate) => candidate.id === 'github' ? github : candidate),
    artifactCards: model.artifactCards.map((card) => (
      card.connector && card.connector.id === 'github' ? { ...card, connector: github } : card
    )),
  }
}

function githubRepositoryCard(model, response) {
  const declared = model.artifactCards.find((card) => (
    card.id === 'github-repositories' && card.kind === 'connector'
  ))
  if (!declared || (declared.connector && declared.connector.id !== 'github')) return null

  const readiness = connectorReadiness(model.connectors, ['github'])
  const connector = model.connectors.find((candidate) => candidate.id === 'github')
  const configured = connector && connector.consent === 'confirmed' && connector.implementation === 'live'
  const readEligible = configured && connector.runtime !== 'needs_attention'
  let badge = 'Needs attention'
  let body = 'GitHub needs attention before Cordia can read repositories.'
  if (readiness === 'ready') {
    badge = 'Available now'
    body = 'GitHub is connected. Open the bounded repository view to review its available repositories.'
  } else if (readiness === 'missing' || readiness === 'connect') {
    badge = 'Setup required'
    body = 'Connect GitHub before Cordia can read repositories in this bounded view.'
  } else if (readiness === 'planned') {
    badge = 'Unavailable'
    body = 'GitHub repository access is not available on this surface yet.'
  }
  const repositories = readEligible ? githubRepositorySummary(response) : null
  if (configured && githubReadFailed(response)) {
    badge = 'Needs attention'
    body = 'GitHub needs attention before Cordia can read repositories. Use the setup page to review or reconnect it.'
  } else if (repositories) {
    badge = 'Live data'
    body = repositories.items.length
      ? `Showing ${repositories.items.length} of up to ${repositories.limit} recently updated repositories.`
      : 'GitHub is connected. No repositories were returned for this bounded view.'
  } else if (readEligible) {
    badge = 'Unavailable'
    body = 'GitHub repository data is unavailable right now. Use the setup page to review or reconnect it.'
  }
  return {
    id: 'github-repository-surface',
    kind: 'github-repositories',
    title: 'GitHub repositories',
    badge,
    body,
    ...(repositories && repositories.items.length ? { items: repositories.items } : {}),
    link: { href: '/github.html', label: 'Open GitHub repositories' },
  }
}

function derivedCards(model) {
  return model.artifactCards
    .filter((card) => card.kind === 'derived')
    .map((card) => ({ id: `derived:${card.id}`, kind: 'derived-note', title: card.title, badge: 'DashView' }))
}

function skillCards(response, connectors) {
  const cards = listFrom(response, 'skills').map((skill) => {
    if (!skill || typeof skill !== 'object' || Array.isArray(skill)) return null
    const id = safeId(skill.id)
    const title = safeText(skill.name)
    const body = safeText(skill.summary, 320)
    const permission = PERMISSIONS.has(skill.permission) ? skill.permission : ''
    const requiredConnectors = connectorIds(skill.required_connectors)
    if (!id || !title || !body || !permission || !requiredConnectors) return null
    const readiness = connectorReadiness(connectors, requiredConnectors)
    const connectorBadge = readinessBadge(readiness)
    const reason = skillActionReason(skill, readiness)
    const request = skillRequest(title)
    if (!request) return null
    return {
      id: `skill:${id}`, kind: 'skill', title, body,
      badge: connectorBadge || (skill.available === true && permission === 'ALLOW'
        ? 'Available now' : permission === 'ASK' ? 'Approval required' : 'Unavailable'),
      action: {
        kind: 'skill', id, request,
        enabled: readiness === 'ready' && skill.available === true && permission === 'ALLOW',
        reason,
      },
    }
  }).filter(Boolean)
  return stable(cards)
}

function capabilityCards(response, connectors) {
  const cards = listFrom(response, 'capabilities').map((capability) => {
    if (!capability || typeof capability !== 'object' || Array.isArray(capability)) return null
    const id = safeId(capability.name)
    const title = safeText(capability.summary, 320)
    const decision = DECISIONS.has(capability.decision) ? capability.decision : ''
    const connectorId = safeId(capability.connector)
    if (!id || !title || !decision || !connectorId) return null
    const readiness = connectorReadiness(connectors, [connectorId])
    return {
      id: `capability:${id}`, kind: 'capability', title,
      badge: decision === 'ALLOW' ? 'Allowed by policy' : decision === 'ASK' ? 'Approval required' : 'Not allowed',
      items: [{ label: 'Connector readiness', meta: readinessDetail(readiness) }],
    }
  }).filter(Boolean)
  return stable(cards)
}

function activityCards(response) {
  return listFrom(response, 'activity').slice(0, 5).map((event, index) => {
    if (!event || typeof event !== 'object' || Array.isArray(event)) return null
    const eventType = safeId(event.event_type)
    const created = typeof event.created === 'string' && event.created.length <= 64 && SAFE_TIMESTAMP.test(event.created)
      ? event.created : ''
    if (!eventType) return null
    return {
      id: `activity:${String(index).padStart(4, '0')}`, kind: 'activity', title: 'Recent account activity',
      items: [{ label: eventType.replaceAll('_', ' '), ...(created ? { meta: created } : {}) }],
    }
  }).filter(Boolean)
}

function inspectionDetail(items) {
  if (!Array.isArray(items)) return ''
  const details = items.slice(0, 6).map((item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return ''
    const label = safeText(item.label, 160)
    const meta = safeText(item.meta, 160)
    if (!label || !meta) return ''
    return `${label}: ${meta}`
  }).filter(Boolean)
  return safeText(details.join(' · '), 600)
}

function inspectionRows(cards, kind, tabId) {
  const rows = []
  for (const card of cards.filter((candidate) => candidate && candidate.kind === kind)) {
    if ((kind === 'context' || kind === 'activity') && Array.isArray(card.items)) {
      for (const item of card.items.slice(0, 20)) {
        if (!item || typeof item !== 'object' || Array.isArray(item)) continue
        const label = safeText(item.label, 160)
        const status = safeText(item.meta, 160)
        const detail = safeText(item.detail, 320)
        if (!label) continue
        rows.push({
          id: `${tabId}-${String(rows.length).padStart(4, '0')}`,
          label,
          ...(status ? { status } : {}),
          ...(detail ? { detail } : {}),
        })
      }
      continue
    }
    const label = safeText(card.title, 160)
    const status = safeText(card.badge, 160)
    const detail = safeText(card.body, 320) || inspectionDetail(card.items)
    if (!label) continue
    rows.push({
      id: `${tabId}-${String(rows.length).padStart(4, '0')}`,
      label,
      ...(status ? { status } : {}),
      ...(detail ? { detail } : {}),
    })
  }
  return rows
}

// This dock is a read-only projection of the already-sanitized renderer model.
// It deliberately drops card actions, links, policy reasons, and activity payloads.
export function inspectionDockModel(rendererModel) {
  const model = rendererModel && typeof rendererModel === 'object' && !Array.isArray(rendererModel)
    ? rendererModel : {}
  const cards = Array.isArray(model.cards) ? model.cards : []
  return {
    tabs: INSPECTION_TABS.map((tab) => {
      const rows = tab.kind ? inspectionRows(cards, tab.kind, tab.id) : []
      let empty = tab.empty
      if (tab.id === 'automations' && model.automationState === 'empty') empty = 'No automations configured'
      if (tab.id === 'context' && model.contextState !== 'empty') empty = 'Context details are unavailable'
      const feedCopy = INSPECTION_FEEDS[tab.id]
      if (feedCopy) {
        const state = model.feedStates && model.feedStates[feedCopy.feed]
        if (state !== 'available') empty = feedCopy[state] || feedCopy.unavailable
      }
      return { id: tab.id, label: tab.label, rows, empty }
    }),
  }
}

function supplementalFeedStates(supplemental) {
  const safeStatus = supplementalFeedStatus(supplemental.feedStatus)
  const states = {}
  for (const feed of ['skills', 'capabilities', 'activity']) {
    const response = supplemental[feed]
    const available = response && typeof response === 'object' && !Array.isArray(response)
      && response.ok === true && Array.isArray(response[feed])
    states[feed] = available ? 'available' : 'unavailable'
    if (safeStatus && safeStatus.unavailable.includes(feed)) states[feed] = safeStatus.state
  }
  return states
}

export function routeFromSearch(search) {
  const params = new URLSearchParams(typeof search === 'string' ? search : '')
  const workspaceId = safeId(params.get('workspace'))
  if (!workspaceId) {
    return { phase: 'missing', workspaceId: '', view: 'workspace', workspaceHref: '', alidoraHref: '' }
  }
  const encoded = encodeURIComponent(workspaceId)
  return {
    phase: 'ready',
    workspaceId,
    view: params.get('view') === 'alidora' ? 'alidora' : 'workspace',
    workspaceHref: `?workspace=${encoded}`,
    alidoraHref: `?workspace=${encoded}&view=alidora`,
  }
}

export function workspaceRendererModel(response, supplemental = {}, expectedWorkspaceId = '') {
  if (!response || typeof response !== 'object' || Array.isArray(response) || response.ok !== true
      || !response.workspace || typeof response.workspace !== 'object' || Array.isArray(response.workspace)
      || !expectedWorkspaceId || response.workspace.id !== expectedWorkspaceId) return null

  const workspace = response.workspace
  const canonical = overlayGithubRuntime(
    workspaceToRendererModel(response), supplemental.github, Object.hasOwn(supplemental, 'github'),
  )
  const context = contextProjection(workspace)
  const cards = [
    missionCard(supplemental.artifacts),
    supplementalFeedStatusCard(supplemental.feedStatus),
    context.card,
    workflowCard(canonical),
    ...agentCards(workspace),
    ...connectorCards(canonical),
    githubRepositoryCard(canonical, supplemental.github),
    ...derivedCards(canonical),
    ...skillCards(supplemental.skills, canonical.connectors),
    ...capabilityCards(supplemental.capabilities, canonical.connectors),
    ...activityCards(supplemental.activity),
  ].filter(Boolean)

  return {
    title: safeText(workspace.title) || 'Cordia Workspace',
    description: safeText(workspace.description, 320),
    cards,
    viewMode: canonical.viewMode,
    contextState: context.state,
    feedStates: supplementalFeedStates(supplemental),
    automationState: Array.isArray(workspace.automations) && workspace.automations.length === 0
      ? 'empty' : 'unavailable',
  }
}

export async function loadWorkspaceTruth(get, workspaceId, errorKind = () => 'error') {
  const id = safeId(workspaceId)
  if (!id || typeof get !== 'function') throw new Error('Invalid workspace request')
  const workspace = await get(`/surveyor/workspace?id=${encodeURIComponent(id)}`)
  const entries = Object.entries(SUPPLEMENTAL_ENDPOINTS)
  const requests = entries.map(([, path]) => get(path))
  const githubRequest = shouldReadGithub(workspace, id) ? get(GITHUB_REPOSITORIES_ENDPOINT) : null
  const githubSettled = githubRequest ? Promise.allSettled([githubRequest]) : null
  const settled = await Promise.allSettled(requests)
  const supplemental = {}
  const unavailable = []
  let rateLimited = false
  settled.forEach((result, index) => {
    const feed = entries[index][0]
    if (result.status === 'fulfilled') supplemental[feed] = result.value
    else {
      unavailable.push(feed)
      try {
        if (errorKind(result.reason) === 'rate-limit') rateLimited = true
      } catch (_error) {
        // Error classifiers are advisory only; the bounded partial state remains safe.
      }
    }
  })
  if (unavailable.length) supplemental.feedStatus = {
    state: rateLimited ? 'rate-limited' : 'partial',
    unavailable,
  }
  if (githubSettled) {
    const github = await githubSettled
    if (github[0].status === 'fulfilled') supplemental.github = github[0].value
    else supplemental.github = { state: 'needs-attention' }
  }
  return { workspace, supplemental }
}

function boundedAssistantText(value) {
  return typeof value === 'string' ? value.trim().slice(0, 6000) : ''
}

export function assistantReplyModel(response) {
  if (!response || typeof response !== 'object' || Array.isArray(response) || response.ok !== true) return null
  const text = safeText(response.output, 6000)
  if (!text) return null
  const limited = Boolean(response.llm && typeof response.llm === 'object' && response.llm.live === false)
  const limitedNote = limited ? safeText(response.llm.note, 240) : ''
  const approvalPending = Boolean(response.approval && typeof response.approval === 'object'
    && !Array.isArray(response.approval) && response.approval.status === 'pending')
  const approvalNote = approvalPending
    ? 'Cordia prepared a draft and paused for your approval. No protected continuation occurred.' : ''
  const note = [approvalNote, limitedNote].filter(Boolean).join(' ')
  return { text, limited, note, ...(approvalPending ? { approvalStatus: 'pending' } : {}) }
}

export function assistantTurnStarted(state, id) {
  const text = boundedAssistantText(state && state.draft)
  if (!text) return state
  return {
    transcript: [...(Array.isArray(state.transcript) ? state.transcript : []), { id, who: 'you', text }],
    draft: '', note: '', busy: true, pending: { id, text },
  }
}

export function assistantTurnFailed(state, note) {
  if (!state || !state.pending) return state
  return {
    transcript: state.transcript.filter((message) => message.id !== state.pending.id),
    draft: state.pending.text,
    note: safeText(note, 240) || 'That message did not get through. Your draft is safe to send again.',
    busy: false,
    pending: null,
  }
}

const SKILL_ACTION_KEYS = ['enabled', 'id', 'kind', 'reason', 'request']

function runnableSkillAction(action) {
  if (!action || typeof action !== 'object' || Array.isArray(action)
      || Object.keys(action).sort().join('|') !== SKILL_ACTION_KEYS.join('|')
      || action.kind !== 'skill' || action.enabled !== true || action.reason !== ''
      || typeof action.id !== 'string' || !/^[a-z][a-z0-9_]{0,79}$/.test(action.id)) return false
  const request = safeText(action.request, 200)
  return request === action.request && /^Run skill: .{1,160}\.$/u.test(request)
}

function skillNameFromRequest(request) {
  const match = /^Run skill: (.{1,160})\.$/u.exec(request)
  return match ? safeText(match[1], 160) : ''
}

function skillTurnStarted(state, operation) {
  return {
    transcript: [...(Array.isArray(state.transcript) ? state.transcript : []), {
      id: operation.id, who: 'you', text: operation.action.request,
    }],
    draft: typeof state.draft === 'string' ? state.draft : '',
    note: '', busy: true,
    pending: { id: operation.id, text: operation.action.request, kind: 'skill', skillId: operation.action.id },
  }
}

function githubSkillReceipt(response, expectedSkillId) {
  if (expectedSkillId !== 'github_repository_review' || !response
      || typeof response !== 'object' || Array.isArray(response)
      || Object.keys(response).sort().join('|') !== 'ok|result|skill_id'
      || response.ok !== true || response.skill_id !== expectedSkillId
      || !response.result || typeof response.result !== 'object' || Array.isArray(response.result)
      || Object.keys(response.result).join('|') !== 'repository_count'
      || !Number.isInteger(response.result.repository_count)
      || response.result.repository_count < 0 || response.result.repository_count > 30) return ''
  const count = response.result.repository_count
  return `Reviewed ${count} GitHub ${count === 1 ? 'repository' : 'repositories'}.`
}

function skillTurnCompleted(state, operation, replyId, response) {
  if (!state || !state.pending || state.pending.kind !== 'skill' || state.pending.id !== operation.id) return state
  const name = skillNameFromRequest(operation.action.request)
  if (!name) return state
  const receipt = githubSkillReceipt(response, operation.action.id)
  return {
    transcript: [...state.transcript, {
      id: replyId, who: 'cordia', text: receipt || `${name} completed.`,
    }],
    draft: state.draft, note: '', busy: false, pending: null,
  }
}

function skillTurnFailed(state, operation, note) {
  if (!state || !state.pending || state.pending.kind !== 'skill' || state.pending.id !== operation.id) return state
  return {
    transcript: state.transcript.filter((message) => message.id !== operation.id),
    draft: state.draft,
    note: safeText(note, 240) || 'That skill did not run. Review its prerequisites and try again.',
    busy: true,
    pending: state.pending,
  }
}

function skillRefreshSettled(state, operation) {
  if (!state || !state.pending || state.pending.kind !== 'skill' || state.pending.id !== operation.id) return state
  return { ...state, busy: false, pending: null }
}

function skillRefreshFailed(state) {
  if (!state || typeof state !== 'object' || Array.isArray(state)) return state
  return {
    ...state,
    note: 'Workspace refresh failed. Reload this page before retrying the skill.',
    busy: false,
    pending: null,
  }
}

function skillFailureCopy(kind) {
  if (kind === 'signed-out') return 'Your session ended. Sign in again before retrying this skill.'
  if (kind === 'offline') return 'Cordia or the required connector is unavailable right now. Workspace status is being refreshed before retry.'
  if (kind === 'rate-limit') return 'Skill limit reached. Wait a few minutes before retrying.'
  if (kind === 'gate') return 'Cordia\'s execution gate did not allow this skill. Review its prerequisites and try again.'
  return 'That skill did not run. Review its prerequisites and try again.'
}

export function createWorkspaceRefreshCoordinator(requestRefresh) {
  let revision = 0
  const pending = new Map()

  function refresh() {
    revision += 1
    const requestedRevision = revision
    return new Promise((resolve, reject) => {
      pending.set(requestedRevision, { resolve, reject })
      try {
        requestRefresh(requestedRevision)
      } catch (error) {
        pending.delete(requestedRevision)
        reject(error)
      }
    })
  }

  function settle(settledRevision, ok) {
    const waiter = pending.get(settledRevision)
    if (!waiter) return
    pending.delete(settledRevision)
    if (ok) waiter.resolve()
    else waiter.reject(new Error('workspace refresh failed'))
  }

  return { refresh, settle }
}

export function createSkillInteractionController({
  executeSkill, errorKind, nextId, operation, updateState, refresh,
}) {
  let refreshSafe = true

  async function execute(pending) {
    let failed = false
    try {
      const response = await executeSkill(pending.action.id)
      if (!response || response.ok !== true) throw new Error('skill execution failed')
      updateState((state) => skillTurnCompleted(state, pending, nextId(), response))
    } catch (error) {
      failed = true
      updateState((state) => skillTurnFailed(state, pending, skillFailureCopy(errorKind(error))))
    }

    try {
      await refresh()
      refreshSafe = true
    } catch (_error) {
      refreshSafe = false
      updateState((state) => skillRefreshFailed(state))
    } finally {
      if (failed) updateState((state) => skillRefreshSettled(state, pending))
      operation.current = ''
    }
  }

  function run(action) {
    if (!runnableSkillAction(action) || operation.current || !refreshSafe) return false
    const pending = { id: nextId(), action }
    operation.current = 'skill'
    updateState((state) => skillTurnStarted(state, pending))
    execute(pending)
    return true
  }

  return { run }
}

export function isAssistantSendKey(event) {
  return Boolean(event && event.key === 'Enter' && !event.shiftKey
    && event.nativeEvent && !event.nativeEvent.isComposing && event.nativeEvent.keyCode !== 229)
}
