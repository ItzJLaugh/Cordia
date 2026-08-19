(function (root, factory) {
  var api = factory()
  if (typeof module === 'object' && module.exports) module.exports = api
  else root.CordiaSurveyorFlow = api
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict'

  function model(payload) {
    var item = payload && payload.onboarding
    if (!payload || payload.ok !== true || !item ||
        item.turn_limit !== 12 || !Number.isInteger(item.turns_used) ||
        !Number.isInteger(item.turns_remaining) ||
        item.turns_used < 0 || item.turns_used > 12 ||
        item.turns_remaining !== 12 - item.turns_used ||
        typeof item.complete !== 'boolean') return { state: 'error' }
    return {
      state: 'ready',
      turnLimit: 12,
      turnsUsed: item.turns_used,
      turnsRemaining: item.turns_remaining,
      complete: item.complete,
    }
  }

  function completionDestination() {
    return 'profile.html#aiSection'
  }

  function reconcileSubmission(turnsBefore, payload) {
    var view = model(payload)
    if (!Number.isInteger(turnsBefore) || turnsBefore < 0 || turnsBefore > 12 ||
        !view || view.state !== 'ready') return { state: 'unknown' }
    if (view.turnsUsed === turnsBefore + 1) return { state: 'saved', view: view }
    if (view.turnsUsed === turnsBefore) return { state: 'retry', view: view }
    return { state: 'unknown' }
  }

  return {
    completionDestination: completionDestination,
    model: model,
    reconcileSubmission: reconcileSubmission,
  }
}))
