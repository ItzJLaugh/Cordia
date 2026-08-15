const SAFE_IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/
const CREDENTIAL_PREFIX = /(?:^|[^A-Za-z0-9])(?:sk-|pk-|rk-|gh[pousr]_|github_pat_|xox[baprs]-|AKIA|(?:api[-_.]?key|access[-_.]?token|token|secret|password|authorization|credential)(?:[-_.:=]|\s*=)|bearer\s+)/i
const LOCAL_PATH = /(?:^|[^A-Za-z0-9_/.])(?:[A-Za-z]:(?:[\\/]|(?=[^\s\\/]))|\\\\[^\s]+|file:\/\/|\/{1,2}(?:[^\s/]+\/)+[^\s/]+)/i
const URL_CANDIDATE = /\b[A-Za-z][A-Za-z0-9+.-]*:\/\/[^\s<>"']+/g
const LOCAL_URL_SCHEMES = new Set(['file:', 'path:'])
const SAFE_SKILL_IDENTIFIER = /^[a-z][a-z0-9_]{0,79}$/
const SAFE_SYNTHETIC_ENTITY_IDENTIFIER = /^(?:agent|skill|connector):([A-Za-z0-9][A-Za-z0-9._-]{0,79})$/

function decodedForInspection(value) {
  try {
    return decodeURIComponent(value)
  } catch {
    return null
  }
}

function urlComponentIsSensitive(value) {
  const decoded = decodedForInspection(value)
  return decoded === null || CREDENTIAL_PREFIX.test(decoded) || LOCAL_PATH.test(decoded)
}

function safeRemoteUrlSpans(value) {
  const spans = []
  URL_CANDIDATE.lastIndex = 0
  let match
  while ((match = URL_CANDIDATE.exec(value))) {
    let url
    try {
      url = new URL(match[0])
    } catch {
      continue
    }
    if (LOCAL_URL_SCHEMES.has(url.protocol)) continue
    if (!url.hostname || url.username || url.password || urlComponentIsSensitive(url.search) || urlComponentIsSensitive(url.hash)) {
      return { spans, unsafe: true }
    }
    spans.push({ start: match.index, end: match.index + match[0].length })
  }
  return { spans, unsafe: false }
}

function hasLocalPathOutsideRemoteUrls(value, spans) {
  let start = 0
  for (const span of spans) {
    if (LOCAL_PATH.test(value.slice(start, span.start))) return true
    start = span.end
  }
  return LOCAL_PATH.test(value.slice(start))
}

export function isSensitiveText(value) {
  if (typeof value !== 'string') return false
  if (CREDENTIAL_PREFIX.test(value)) return true
  const remoteUrls = safeRemoteUrlSpans(value)
  return remoteUrls.unsafe || hasLocalPathOutsideRemoteUrls(value, remoteUrls.spans)
}

export function isCredentialShapedIdentifier(value) {
  return typeof value === 'string' && CREDENTIAL_PREFIX.test(value)
}

export function isSafeIdentifier(value) {
  return typeof value === 'string' && SAFE_IDENTIFIER.test(value)
    && !isSensitiveText(value)
}

export function isSafeSkillIdentifier(value) {
  return typeof value === 'string' && SAFE_SKILL_IDENTIFIER.test(value)
    && !isSensitiveText(value)
}

export function isSafeSyntheticEntityIdentifier(value) {
  if (typeof value !== 'string' || value.length > 96 || isSensitiveText(value)) return false
  const match = SAFE_SYNTHETIC_ENTITY_IDENTIFIER.exec(value)
  return Boolean(match && isSafeIdentifier(match[1]))
}
