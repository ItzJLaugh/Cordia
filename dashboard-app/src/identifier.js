const SAFE_IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/
const CREDENTIAL_PREFIX = /(?:^|[^A-Za-z0-9])(?:sk-|pk-|rk-|gh[pousr]_|github_pat_|xox[baprs]-|AKIA|(?:api[-_.]?key|access[-_.]?token|token|secret|password|authorization|credential)(?:[-_.:=]|\s*=)|bearer\s+)/i
const LOCAL_PATH = /(?:^|[^A-Za-z0-9_/.])(?:[A-Za-z]:(?:[\\/]|(?=[^\s\\/]))|\\\\[^\s]+|file:\/\/|\/{1,2}(?:[^\s/]+\/)+[^\s/]+)/i
const REMOTE_URL = /\b(?!(?:file|path):)[A-Za-z][A-Za-z0-9+.-]*:\/\/(?:localhost|[A-Za-z0-9][A-Za-z0-9.-]*)(?::\d{1,5})?(?:[/?#][^\s]*)?/gi
const REMOTE_URL_WITH_USERINFO = /\b(?!(?:file|path):)[A-Za-z][A-Za-z0-9+.-]*:\/\/[^/\s?#]*@/i
const SAFE_SKILL_IDENTIFIER = /^[a-z][a-z0-9_]{0,79}$/
const SAFE_SYNTHETIC_ENTITY_IDENTIFIER = /^(?:agent|skill|connector):([A-Za-z0-9][A-Za-z0-9._-]{0,79})$/

export function isSensitiveText(value) {
  return typeof value === 'string' && (
    CREDENTIAL_PREFIX.test(value)
    || REMOTE_URL_WITH_USERINFO.test(value)
    || LOCAL_PATH.test(value.replace(REMOTE_URL, ''))
  )
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
