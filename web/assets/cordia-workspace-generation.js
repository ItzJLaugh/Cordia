(function (root, factory) {
  var api = factory()
  if (typeof module === 'object' && module.exports) module.exports = api
  else root.CordiaWorkspaceGeneration = api
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict'

  async function generate(options) {
    try {
      if (!options || typeof options.fetch !== 'function' || !options.navigation ||
          typeof options.navigation.buildWorkspaceNavigation !== 'function') {
        throw new Error('generation failed')
      }
      var response = await options.fetch('/surveyor/workspace/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: '{}',
      })
      var payload = await response.json().catch(function () { return null })
      if (!response.ok || !payload || payload.ok !== true ||
          typeof payload.created !== 'boolean' ||
          Object.keys(payload).sort().join('|') !== 'created|id|ok') {
        throw new Error('generation failed')
      }
      var target = options.navigation.buildWorkspaceNavigation(payload.id)
      if (!target || typeof target.href !== 'string') {
        throw new Error('generation failed')
      }
      return { id: payload.id, href: target.href, created: payload.created }
    } catch (_) {
      throw new Error('generation failed')
    }
  }

  return { generate: generate }
}))
