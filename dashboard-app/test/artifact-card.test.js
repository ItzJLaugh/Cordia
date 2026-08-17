import assert from 'node:assert/strict'
import test from 'node:test'

import React from 'react'
import TestRenderer, { act } from 'react-test-renderer'

async function render(component, props) {
  const originalConsoleError = console.error
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  console.error = (...args) => {
    if (args[0] !== 'react-test-renderer is deprecated. See https://react.dev/warnings/react-test-renderer') {
      originalConsoleError(...args)
    }
  }
  let renderer
  try {
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(component, props))
    })
    return renderer
  } finally {
    console.error = originalConsoleError
  }
}

test('GitHub artifact renders only the fixed same-origin repository route', async () => {
  const linkModule = await import('../src/ArtifactLink.js').catch(() => null)
  assert.ok(linkModule, 'the fixed artifact link control must be directly render-testable')
  const safeLink = { href: '/github.html', label: 'Open GitHub repositories' }
  const renderer = await render(linkModule.default, { link: safeLink })
  try {
    const links = renderer.root.findAllByType('a')
    assert.equal(links.length, 1)
    assert.equal(links[0].props.href, '/github.html')
    assert.equal(links[0].children.join(''), 'Open GitHub repositories')
    assert.equal(links[0].props.target, undefined)
  } finally {
    await act(async () => { renderer.unmount() })
  }

  for (const link of [
    { href: 'https://example.test/private', label: 'External' },
    { href: '/github.html?token=private', label: 'Query token' },
    { href: '/surveyor/github/repositories', label: 'Raw endpoint' },
  ]) {
    const blocked = await render(linkModule.default, { link })
    try {
      assert.equal(blocked.root.findAllByType('a').length, 0, link.href)
    } finally {
      await act(async () => { blocked.unmount() })
    }
  }
})

test('repository artifact renders the bounded summary detail projected by the workspace model', async () => {
  const itemModule = await import('../src/ArtifactItems.js').catch(() => null)
  assert.ok(itemModule, 'the production artifact item list must be directly render-testable')
  const renderer = await render(itemModule.default, {
    items: [{
      label: 'ItzJLaugh/Cordia', meta: 'Private · main · Updated 2026-08-16',
      detail: 'Primary agent workspace.',
    }],
  })
  try {
    const detail = renderer.root.findByProps({ className: 'artifact-item-detail' })
    assert.equal(detail.children.join(''), 'Primary agent workspace.')
  } finally {
    await act(async () => { renderer.unmount() })
  }
})
