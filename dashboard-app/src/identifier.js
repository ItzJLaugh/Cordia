const SAFE_IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/
const CREDENTIAL_SHAPED_IDENTIFIER = /^(?:(?:sk|pk|rk)-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|github_pat_[A-Za-z0-9_]{20,}|(?:api[-_.]?key|access[-_.]?token|token|secret|password|credential)[-_.])/i
const SAFE_SKILL_IDENTIFIER = /^[a-z][a-z0-9_]{0,79}$/

export function isCredentialShapedIdentifier(value) {
  return typeof value === 'string' && CREDENTIAL_SHAPED_IDENTIFIER.test(value)
}

export function isSafeIdentifier(value) {
  return typeof value === 'string' && SAFE_IDENTIFIER.test(value)
    && !isCredentialShapedIdentifier(value)
}

export function isSafeSkillIdentifier(value) {
  return typeof value === 'string' && SAFE_SKILL_IDENTIFIER.test(value)
    && !isCredentialShapedIdentifier(value)
}
