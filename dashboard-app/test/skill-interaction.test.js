import assert from 'node:assert/strict'
import test from 'node:test'

import React from 'react'
import TestRenderer, { act } from 'react-test-renderer'

import * as workspaceView from '../src/workspace-view.js'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((pass, fail) => {
    resolve = pass
    reject = fail
  })
  return { promise, resolve, reject }
}

async function renderedControl(module, props) {
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
      renderer = TestRenderer.create(React.createElement(module.default, props))
    })
    return renderer
  } finally {
    console.error = originalConsoleError
  }
}

test('a rendered runnable skill click submits immediately once and records only bounded transcript text', async () => {
  const controlModule = await import('../src/SkillAction.js').catch(() => null)
  assert.ok(controlModule, 'the production skill action control must be directly render-testable')
  assert.equal(typeof workspaceView.createSkillInteractionController, 'function')

  const execution = deferred()
  const calls = []
  const operation = { current: '' }
  let refreshes = 0
  let state = { transcript: [], draft: '', note: '', busy: false, pending: null }
  const updateState = (update) => { state = update(state) }
  const controller = workspaceView.createSkillInteractionController({
    executeSkill(id) {
      calls.push(id)
      return execution.promise
    },
    errorKind: () => 'error',
    nextId: (() => { let id = 0; return () => ++id })(),
    operation,
    updateState,
    refresh: () => { refreshes += 1 },
  })
  const action = {
    kind: 'skill', id: 'github_repository_review',
    request: 'Run skill: Review GitHub repositories.', enabled: true, reason: '',
  }
  const renderer = await renderedControl(controlModule, { action, busy: false, onAction: controller.run })
  try {
    const button = renderer.root.findByProps({ 'data-skill-action': 'github_repository_review' })
    await act(async () => {
      button.props.onClick()
      button.props.onClick()
    })
    assert.deepEqual(calls, ['github_repository_review'])
    assert.deepEqual(state.transcript, [{ id: 1, who: 'you', text: 'Run skill: Review GitHub repositories.' }])
    assert.equal(state.busy, true)

    execution.resolve({
      ok: true,
      skill: { name: 'Injected name', prompt: 'Do not render this prompt' },
      capability: { authorization: 'Do not render this authorization' },
      result: { token: 'Do not render this result' },
    })
    await execution.promise
    await new Promise((resolve) => setTimeout(resolve, 0))

    assert.deepEqual(state.transcript, [
      { id: 1, who: 'you', text: 'Run skill: Review GitHub repositories.' },
      { id: 2, who: 'cordia', text: 'Review GitHub repositories completed.' },
    ])
    assert.equal(state.busy, false)
    assert.equal(refreshes, 1)
    assert.equal(JSON.stringify(state).includes('Injected name'), false)
    assert.equal(JSON.stringify(state).includes('Do not render'), false)
  } finally {
    await act(async () => { renderer.unmount() })
  }
})

test('blocked skill cards render truthful status without an execution control', async () => {
  const controlModule = await import('../src/SkillAction.js').catch(() => null)
  assert.ok(controlModule, 'the production skill action control must be directly render-testable')
  const reasons = [
    'This skill is not available through its declared capability.',
    'Approval is required. This web view cannot continue the protected external action.',
    'Cordia policy does not allow this skill.',
    'A required connector is not available in this workspace.',
    'This skill is planned for a desktop or local surface and is not available here.',
    'A required connector needs attention before this skill can run.',
  ]

  for (const [index, reason] of reasons.entries()) {
    const renderer = await renderedControl(controlModule, {
      action: {
        kind: 'skill', id: `blocked_skill_${index}`, request: `Run skill: Blocked skill ${index}.`,
        enabled: false, reason,
      },
      busy: false,
      onAction: () => assert.fail('blocked action must not be invokable'),
    })
    try {
      assert.equal(renderer.root.findAllByType('button').length, 0)
      assert.equal(renderer.root.findByProps({ role: 'status' }).children.join(''), reason)
    } finally {
      await act(async () => { renderer.unmount() })
    }
  }
})

test('a failed skill request is withdrawn, restores a retryable action, and uses bounded gate copy', async () => {
  assert.equal(typeof workspaceView.createSkillInteractionController, 'function')
  const first = deferred()
  const calls = []
  const operation = { current: '' }
  let state = { transcript: [], draft: '', note: '', busy: false, pending: null }
  const controller = workspaceView.createSkillInteractionController({
    executeSkill(id) {
      calls.push(id)
      return calls.length === 1 ? first.promise : Promise.resolve({ ok: true })
    },
    errorKind: () => 'gate',
    nextId: (() => { let id = 10; return () => ++id })(),
    operation,
    updateState: (update) => { state = update(state) },
    refresh: () => {},
  })
  const action = {
    kind: 'skill', id: 'github_repository_review',
    request: 'Run skill: Review GitHub repositories.', enabled: true, reason: '',
  }

  assert.equal(controller.run(action), true)
  first.reject(new Error('authorization=private-policy-detail'))
  await first.promise.catch(() => {})
  await new Promise((resolve) => setTimeout(resolve, 0))
  assert.deepEqual(state.transcript, [])
  assert.equal(state.busy, false)
  assert.equal(operation.current, '')
  assert.equal(state.note, 'Cordia\'s execution gate did not allow this skill. Review its prerequisites and try again.')
  assert.equal(controller.run(action), true)
  await new Promise((resolve) => setTimeout(resolve, 0))
  assert.deepEqual(calls, ['github_repository_review', 'github_repository_review'])
})

test('skill failures use bounded signed-out and offline copy without transport details', async () => {
  const cases = [
    ['signed-out', 'Your session ended. Sign in again before retrying this skill.'],
    ['offline', 'The server is unreachable right now. Retry this skill when Cordia is available.'],
  ]
  const action = {
    kind: 'skill', id: 'github_repository_review',
    request: 'Run skill: Review GitHub repositories.', enabled: true, reason: '',
  }

  for (const [kind, expected] of cases) {
    const operation = { current: '' }
    let state = { transcript: [], draft: '', note: '', busy: false, pending: null }
    const controller = workspaceView.createSkillInteractionController({
      executeSkill: () => Promise.reject(new Error('token=private-transport-detail')),
      errorKind: () => kind,
      nextId: (() => { let id = 20; return () => ++id })(),
      operation,
      updateState: (update) => { state = update(state) },
      refresh: () => assert.fail('failed execution must not refresh workspace truth'),
    })

    assert.equal(controller.run(action), true)
    await new Promise((resolve) => setTimeout(resolve, 0))
    assert.deepEqual(state.transcript, [])
    assert.equal(state.note, expected)
    assert.equal(JSON.stringify(state).includes('private-transport-detail'), false)
  }
})
