import { isSafeIdentifier, isSafeSkillIdentifier } from './identifier.js'

const API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  ? 'http://127.0.0.1:9995'
  : ''

class ApiResponseError extends Error {
  constructor(message, kind = 'error') {
    super(message)
    this.kind = kind
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

function responseKind(status) {
  if (status === 401 || status === 403) return 'signed-out'
  if (status === 409) return 'gate'
  if (status === 429) return 'rate-limit'
  if (status === 503) return 'offline'
  return 'error'
}

async function validatedRequest(path, options) {
  try {
    const response = await fetch(API + path, options)
    const body = await response.json().catch(() => null)
    if (!response.ok || !body || body.ok !== true) {
      throw new ApiResponseError(safeServerError(body && body.error), responseKind(response.status))
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
export async function postRun(workspaceId, input) {
  if (!isSafeIdentifier(workspaceId)) {
    throw new ApiResponseError('Invalid workspace request', 'error')
  }
  const headers = { 'Content-Type': 'application/json' }
  const devToken = localStorage.getItem('cordia-dev-token')
  if (devToken) headers.Authorization = `Bearer ${devToken}`
  const boundedText = typeof input === 'string' ? input.trim().slice(0, 6000) : ''
  return validatedRequest('/surveyor/run', {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify({ id: workspaceId, input: boundedText }),
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
