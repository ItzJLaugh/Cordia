/* Fail-closed renderer model for Cordia's non-scored Surveyor operator profile. */
(function (root, factory) {
  var api = factory()
  if (typeof module === 'object' && module.exports) module.exports = api
  root.CordiaOperatorProfile = api
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict'

  var TITLE = 'What Cordia currently understands'
  var ERROR = 'Cordia could not load this profile safely. Try again.'
  var IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/
  var CONNECTOR_ID = /^[a-z][a-z0-9_]{0,79}$/
  var CREDENTIAL = /(?:^|[^A-Za-z0-9])(?:sk-|pk-|rk-|gh[pousr]_|github_pat_|xox[baprs]-|AKIA|(?:api[-_.]?key|access[-_.]?token|token|secret|password|authorization|credential)(?:[-_.:=]|\s*=)|bearer\s+|-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----)/i
  var LOCAL_PATH = /(?:^|[^A-Za-z0-9_/.])(?:[A-Za-z]:(?:[\\/]|(?=[^\s\\/]))|\\\\[^\s]+|file:\/\/|path:\/\/|\.{1,2}[\\/][^\s]+|\/(?:tmp|home|Users|var|etc|opt|srv|run|mnt|workspace|Library)(?:\/[^\s]*)?|\/{1,2}(?:[^\s/]+\/)+[^\s/]+)/i
  var URL_CANDIDATE = /\b[A-Za-z][A-Za-z0-9+.-]*:\/\/[^\s<>"']+/g
  var STRENGTH = new Set(['clear', 'emerging', 'early'])
  var ACTION = new Set(['continue_survey', 'refine_profile', 'create_interface'])

  function decoded(value) {
    try { return decodeURIComponent(value) } catch (_) { return null }
  }

  function sensitiveUrlPart(value) {
    var inspected = decoded(value)
    return inspected == null || CREDENTIAL.test(inspected) || LOCAL_PATH.test(inspected)
  }

  function isSensitiveText(value) {
    if (typeof value !== 'string') return false
    if (CREDENTIAL.test(value)) return true
    URL_CANDIDATE.lastIndex = 0
    var spans = []
    var match
    while ((match = URL_CANDIDATE.exec(value))) {
      var url
      try { url = new URL(match[0]) } catch (_) { return true }
      if (url.protocol === 'file:' || url.protocol === 'path:' || !url.hostname ||
          url.username || url.password || sensitiveUrlPart(url.search) || sensitiveUrlPart(url.hash)) return true
      spans.push({ start: match.index, end: match.index + match[0].length })
    }
    var remainder = ''
    var start = 0
    spans.forEach(function (span) {
      remainder += value.slice(start, span.start)
      start = span.end
    })
    remainder += value.slice(start)
    return LOCAL_PATH.test(remainder)
  }

  function safeText(value, limit) {
    if (typeof value !== 'string') return ''
    var text = value.replace(/\s+/g, ' ').trim()
    return text && text.length <= limit && !isSensitiveText(text) ? text : ''
  }

  function safeIdentifier(value) {
    return typeof value === 'string' && IDENTIFIER.test(value) && !isSensitiveText(value)
  }

  function identifiers(items) {
    return (Array.isArray(items) ? items : []).slice(0, 3).flatMap(function (item) {
      if (!item || typeof item !== 'object') return []
      var name = safeText(item.name, 80)
      var meaning = safeText(item.meaning, 240)
      var useAi = safeText(item.use_ai_this_way, 240)
      if (!name || !meaning || !useAi || !STRENGTH.has(item.evidence_strength)) return []
      return [{ name: name, meaning: meaning, useAiThisWay: useAi, evidenceStrength: item.evidence_strength }]
    })
  }

  function labelled(items) {
    return (Array.isArray(items) ? items : []).slice(0, 6).flatMap(function (item) {
      if (!item || typeof item !== 'object') return []
      var label = safeText(item.label, 80)
      var value = safeText(item.value, 240)
      return label && value ? [{ label: label, value: value }] : []
    })
  }

  function evidence(items) {
    return (Array.isArray(items) ? items : []).slice(0, 6).flatMap(function (item) {
      if (!item || typeof item !== 'object') return []
      var summary = safeText(item.summary, 280)
      return summary && STRENGTH.has(item.evidence_strength)
        ? [{ summary: summary, evidenceStrength: item.evidence_strength }]
        : []
    })
  }

  function connectors(items) {
    return (Array.isArray(items) ? items : []).slice(0, 12).flatMap(function (item) {
      if (!item || typeof item !== 'object') return []
      var name = safeText(item.name, 80)
      if (!CONNECTOR_ID.test(item.id || '') || !name ||
          !['Confirmed by user', 'Suggested - not connected'].includes(item.status) ||
          !['live', 'planned'].includes(item.implementation_status)) return []
      return [{ id: item.id, name: name, status: item.status, implementationStatus: item.implementation_status }]
    })
  }

  function learning(items) {
    return (Array.isArray(items) ? items : []).slice(0, 5)
      .map(function (item) { return safeText(item, 160) }).filter(Boolean)
  }

  function nextAction(item) {
    if (!item || typeof item !== 'object' || !ACTION.has(item.type)) return null
    var label = safeText(item.label, 80)
    var reason = safeText(item.reason, 240)
    return label && reason ? { type: item.type, label: label, reason: reason } : null
  }

  function workspace(item, navigation) {
    if (!item || typeof item !== 'object' || !safeIdentifier(item.id) || !navigation ||
        typeof navigation.buildWorkspaceNavigation !== 'function') return null
    var target = navigation.buildWorkspaceNavigation(item.id)
    var name = safeText(item.name, 80)
    return target && name ? { id: item.id, name: name, href: target.href } : null
  }

  function errorModel() {
    return { state: 'error', message: ERROR }
  }

  function buildOperatorProfileModel(payload, navigation) {
    if (!payload || payload.ok !== true || !payload.operator_profile ||
        typeof payload.operator_profile !== 'object') return errorModel()
    var source = payload.operator_profile
    if (source.title !== TITLE || isSensitiveText(source.title)) return errorModel()
    var action = nextAction(source.next_action)
    if (!action) return errorModel()
    var latest = workspace(source.latest_workspace, navigation)
    var primary
    var secondary = null
    if (latest) {
      primary = { kind: 'link', label: 'Open ' + latest.name, href: latest.href }
      if (action.type !== 'create_interface') secondary = { kind: 'surveyor', label: 'Refine with Surveyor' }
    } else if (action.type === 'create_interface') {
      primary = { kind: 'link', label: 'Build this workspace', href: 'builder.html?from=surveyor' }
    } else {
      primary = { kind: 'surveyor', label: action.label }
    }
    return {
      state: 'ready',
      title: TITLE,
      identifiers: identifiers(source.identifiers),
      understanding: labelled(source.understanding),
      evidence: evidence(source.evidence),
      connectors: connectors(source.connectors),
      stillLearning: learning(source.still_learning),
      nextAction: action,
      primaryAction: primary,
      secondaryAction: secondary,
    }
  }

  return { buildOperatorProfileModel: buildOperatorProfileModel, isSensitiveText: isSensitiveText }
})
