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

  return {
    completionDestination: completionDestination,
    model: model,
  }
}))
