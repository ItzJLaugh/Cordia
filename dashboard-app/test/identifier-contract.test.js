import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import test from 'node:test'

import { routeFromSearch } from '../src/workspace-view.js'

const require = createRequire(import.meta.url)
const { buildWorkspaceNavigation } = require('../../web/assets/workspace-navigation.js')

test('legacy navigation and the dashboard route enforce one safe workspace-id contract', () => {
  const cases = [
    ['workspace-1', true],
    ['0f1234567890abcdef1234567890abcd', true],
    ['C:drive-relative', false],
    ['C:\\private\\workspace', false],
    ['/home/cordia/private', false],
    ['sk-abcdefghijk', false],
    ['ghp_abcdefghijklmnopqrstuvwxyz', false],
    ['github_pat_abcdefghijklmnopqrstuvwxyz0123456789', false],
    ['AKIA1234567890ABCDEF', false],
    ['token.secret-value', false],
    ['a'.repeat(81), false],
  ]

  for (const [workspaceId, expected] of cases) {
    const legacyAccepts = buildWorkspaceNavigation(workspaceId) !== null
    const dashboardRoute = routeFromSearch(`?workspace=${encodeURIComponent(workspaceId)}`)
    const dashboardAccepts = dashboardRoute.phase === 'ready'
    assert.equal(legacyAccepts, expected, `legacy ${workspaceId}`)
    assert.equal(dashboardAccepts, expected, `dashboard ${workspaceId}`)
    assert.equal(dashboardAccepts, legacyAccepts, `agreement ${workspaceId}`)
    if (!expected) {
      assert.equal(dashboardRoute.workspaceHref, '', `no query URL for ${workspaceId}`)
      assert.equal(dashboardRoute.alidoraHref, '', `no advanced query URL for ${workspaceId}`)
    }
  }
})
