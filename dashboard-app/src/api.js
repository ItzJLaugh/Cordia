import { isSafeIdentifier, isSafeSkillIdentifier } from './identifier.js'

const API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  ? 'http://127.0.0.1:9995'
  : ''

const INTENT_MISS_CATEGORIES = new Set([
  'missing_context', 'wrong_audience', 'too_generic', 'needs_evidence',
  'wrong_format', 'wrong_constraint', 'unsafe_to_automate',
  'needs_human_checkpoint',
])

class ApiResponseError extends Error {
  constructor(message, kind = 'error', definitive = false) {
    super(message)
    this.kind = kind
    this.definitive = definitive
  }
}

function safeServerError(value) {
  return typeof value === 'string'
    && value.length <= 160
    && /^[A-Za-z0-9][A-Za-z0-9 .,'!?-]*$/.test(value)
    ? value
    : 'Request failed'
}

export function safeErrorMessage(error) {
  return error instanceof ApiResponseError ? error.message : 'Request failed'
}

export function apiErrorKind(error) {
  return error instanceof ApiResponseError ? error.kind : 'offline'
}

function responseKind(status, body) {
  if (status === 401 || status === 403) return 'signed-out'
  if (status === 409 && body && typeof body === 'object' && !Array.isArray(body)
      && Object.keys(body).sort().join('|') === 'error|ok'
      && body.ok === false && body.error === 'revision_conflict') return 'revision-conflict'
  if (status === 402 && body && typeof body === 'object' && !Array.isArray(body)
      && Object.keys(body).sort().join('|') === 'code|error|limit|ok|used'
      && body.ok === false
      && body.error === 'Free agent actions used. Upgrade to continue.'
      && body.code === 'usage_limit' && body.used === 10 && body.limit === 10) return 'usage-limit'
  if (status === 429) return 'rate-limit'
  if (status === 503) return 'offline'
  return 'error'
}

async function validatedRequest(path, options) {
  try {
    const response = await fetch(API + path, options)
    const body = await response.json().catch(() => null)
    if (!response.ok || !body || body.ok !== true) {
      const kind = responseKind(response.status, body)
      throw new ApiResponseError(safeServerError(body && body.error), kind,
        response.status >= 400 && response.status < 500 && kind !== 'revision-conflict')
    }
    return body
  } catch (error) {
    if (error instanceof ApiResponseError) throw error
    throw new ApiResponseError('Request failed', 'offline')
  }
}

// Authenticated Surveyor reads share one bounded response contract. The
// HttpOnly session cookie stays in the browser; a manually supplied
// local-development token remains useful for the documented dev setup.
export async function getApi(path) {
  const headers = {}
  const devToken = localStorage.getItem('cordia-dev-token')
  if (devToken) headers.Authorization = `Bearer ${devToken}`
  return validatedRequest(path, {
    method: 'GET',
    headers,
    credentials: 'include',
  })
}

// Ordinary assistant submission has one fixed transport contract. It cannot
// select another method, URL, or header surface.
export async function postRun(workspaceId, revision, message, idempotencyKey) {
  if (!isSafeIdentifier(workspaceId) || !Number.isInteger(revision) || revision < 0
      || !isSafeIdentifier(idempotencyKey)) {
    throw new ApiResponseError('Invalid workspace request', 'error')
  }
  const headers = { 'Content-Type': 'application/json' }
  const devToken = localStorage.getItem('cordia-dev-token')
  if (devToken) headers.Authorization = `Bearer ${devToken}`
  const boundedText = typeof message === 'string' ? message.trim().slice(0, 6000) : ''
  if (!boundedText) throw new ApiResponseError('Invalid workspace request', 'error')
  return validatedRequest('/surveyor/run', {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify({ id: workspaceId, revision, message: boundedText, idempotency_key: idempotencyKey }),
  })
}

// Skill execution has one fixed mutation contract. The caller can select only
// a registered-looking identifier; the server remains the execution authority.
export async function postSkillExecute(skillId) {
  if (!isSafeSkillIdentifier(skillId)) {
    throw new ApiResponseError('Invalid skill request', 'error')
  }
  const headers = { 'Content-Type': 'application/json' }
  const devToken = localStorage.getItem('cordia-dev-token')
  if (devToken) headers.Authorization = `Bearer ${devToken}`
  return validatedRequest('/surveyor/skill/execute', {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify({ id: skillId }),
  })
}

// Sign-out is intentionally fixed to the existing cookie-backed endpoint. It
// accepts no caller-selected path, payload, or authorization header.
export async function postLogout() {
  return validatedRequest('/auth/logout', {
    method: 'POST',
    credentials: 'include',
  })
}

// Intent correction has one fixed structured write contract. The server owns
// profile persistence and artifact recompilation; the renderer can submit only
// a known category and bounded user-authored guidance.
export async function postIntentMiss(category, correction, effect) {
  const boundedCorrection = typeof correction === 'string' ? correction.trim().slice(0, 600) : ''
  const boundedEffect = typeof effect === 'string' ? effect.trim().slice(0, 600) : ''
  if (!INTENT_MISS_CATEGORIES.has(category) || !boundedCorrection || !boundedEffect) {
    throw new ApiResponseError('Invalid correction request', 'error')
  }
  const headers = { 'Content-Type': 'application/json' }
  const devToken = localStorage.getItem('cordia-dev-token')
  if (devToken) headers.Authorization = `Bearer ${devToken}`
  return validatedRequest('/surveyor/intent-miss', {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify({
      category,
      correction: boundedCorrection,
      effect: boundedEffect,
    }),
  })
}
