import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import test from 'node:test'

import { routeFromSearch } from '../src/workspace-view.js'
import { isSafeIdentifier, isSafeSyntheticEntityIdentifier, isSensitiveText } from '../src/identifier.js'

const require = createRequire(import.meta.url)
const { buildWorkspaceNavigation } = require('../../web/assets/workspace-navigation.js')

test('shared renderer text boundary rejects metadata-prefixed local paths without rejecting bounded labels', () => {
  const localPaths = [
    'path:C:\\private\\workspace',
    'path:C:private',
    'path:/home/cordia/private',
    'file:///home/cordia/private',
    'path:\\\\server\\private',
    'path:/root/.ssh',
    'path:/Users/cordia/private',
    'path:/private/var/db',
    'path:/System/Library',
    'path:/etc/hosts',
    'path:/usr/local/bin',
    'path:/run/secrets/key',
    'path:/srv/cordia/private',
    'path:/mnt/c/private',
    'path:/workspace/private',
    'path:/Library/Keychains',
    'path://server/share',
  ]

  for (const value of localPaths) assert.equal(isSensitiveText(value), true, value)

  for (const value of ['Ordinary workspace text', 'CI/CD pipeline', 'workspace-1', 'agent:review']) {
    assert.equal(isSensitiveText(value), false, value)
  }
  assert.equal(isSafeIdentifier('workspace-1'), true)
  assert.equal(isSafeSyntheticEntityIdentifier('agent:review'), true)
})

test('shared renderer text boundary preserves complete remote URLs but rejects remote credentials', () => {
  const remoteUrls = [
    'https://example.test/docs/start',
    'http://localhost:8000/api/v1',
    'ftp://files.example.test/public/readme',
    'custom://host/one/two',
    'https://[2001:db8::1]/docs/start',
  ]

  for (const value of remoteUrls) assert.equal(isSensitiveText(value), false, value)
  for (const value of [
    'https://user:password@example.test/docs/start',
    'https://example.test/docs/start?token=private',
    'file:///home/cordia/private',
    'path://server/share',
    'https://example.test/docs?next=file:///home/cordia/private',
    'https://example.test/docs?next=path://server/share',
    'https://example.test/docs?local=path:C:\\private\\workspace',
    'https://example.test/docs?home=/home/cordia/private',
    'https://example.test/docs?home=%2Fhome%2Fcordia%2Fprivate',
  ]) assert.equal(isSensitiveText(value), true, value)
})

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
