import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import React from 'react'
import TestRenderer, { act } from 'react-test-renderer'

import InspectionDock from '../src/InspectionDock.js'
import { inspectionDockModel, workspaceRendererModel } from '../src/workspace-view.js'

const canonical = {
  ok: true,
  workspace: {
    id: 'workspace-1',
    title: 'Launch workspace',
    automations: [],
    windows: [
      { id: 'notes', kind: 'derived', title: 'Evidence notes' },
      { id: 'github-repositories', kind: 'connector', connector_id: 'github', title: 'GitHub repositories' },
    ],
    workflow: { steps: [] },
    agents: [],
    connectors: [{
      id: 'github', status: 'confirmed', implementation_status: 'live', lifecycle: 'live', runtime_status: 'live',
    }],
    context_sources: [{ kind: 'github_repository', id: 'CordiaHQ/product', label: 'CordiaHQ/product' }],
  },
}

const supplemental = {
  skills: {
    ok: true,
    skills: [{
      id: 'github_repository_review', name: 'Review repositories', summary: 'Collect repository metadata.',
      permission: 'ALLOW', available: true, required_connectors: ['github'],
      action_secret: 'must-not-render',
    }],
  },
  capabilities: {
    ok: true,
    capabilities: [{
      name: 'github.read_repositories', summary: 'Read repository metadata.', decision: 'ALLOW',
      connector: 'github', reason: 'internal policy reason must not render',
    }],
  },
  activity: {
    ok: true,
    activity: [{
      event_type: 'interface_run', created: '2026-08-18T10:00:00Z',
      payload: { prompt: 'private prompt must not render' },
    }],
  },
}

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

test('inspectionDockModel emits exactly six stable renderer-safe tabs and keeps action data out', () => {
  const rendererModel = workspaceRendererModel(canonical, supplemental, 'workspace-1')
  const dock = inspectionDockModel(rendererModel)

  assert.deepEqual(dock.tabs.map(({ id, label }) => ({ id, label })), [
    { id: 'connected', label: 'Connected' },
    { id: 'skills', label: 'Skills' },
    { id: 'access', label: 'Access' },
    { id: 'context', label: 'Context' },
    { id: 'automations', label: 'Automations' },
    { id: 'activity', label: 'Activity' },
  ])
  assert.deepEqual(dock.tabs.map((tab) => tab.rows.map((row) => row.label)), [
    ['github'],
    ['Review repositories'],
    ['Read repository metadata.'],
    ['CordiaHQ/product'],
    [],
    ['interface run'],
  ])
  assert.equal(dock.tabs[4].empty, 'No automations configured')
  const serialized = JSON.stringify(dock)
  for (const blocked of ['action', 'request', 'reason', 'internal policy', 'private prompt', 'must-not-render']) {
    assert.equal(serialized.includes(blocked), false, blocked)
  }
})

test('inspectionDockModel has truthful bounded empty states and fails closed for unknown automation shapes', () => {
  const cases = [
    { automations: undefined, message: 'Automation details are unavailable' },
    { automations: {}, message: 'Automation details are unavailable' },
    { automations: [{ id: 'daily-secret', token: 'must-not-render' }], message: 'Automation details are unavailable' },
  ]
  for (const scenario of cases) {
    const response = structuredClone(canonical)
    if (scenario.automations === undefined) delete response.workspace.automations
    else response.workspace.automations = scenario.automations
    const dock = inspectionDockModel(workspaceRendererModel(response, {}, 'workspace-1'))
    const automations = dock.tabs.find((tab) => tab.id === 'automations')
    assert.equal(automations.empty, scenario.message)
    assert.deepEqual(automations.rows, [])
    assert.equal(JSON.stringify(dock).includes('daily-secret'), false)
    assert.equal(JSON.stringify(dock).includes('must-not-render'), false)
  }

  const empty = inspectionDockModel(workspaceRendererModel({
    ok: true,
    workspace: {
      id: 'workspace-1', title: 'Empty', automations: [], windows: [], connectors: [], context_sources: [],
    },
  }, {
    skills: { ok: true, skills: [] },
    capabilities: { ok: true, capabilities: [] },
    activity: { ok: true, activity: [] },
  }, 'workspace-1'))
  assert.deepEqual(empty.tabs.map((tab) => tab.empty), [
    'No connectors available',
    'No skills available',
    'No access decisions available',
    'No context available',
    'No automations configured',
    'No recent account activity',
  ])
})

test('inspection dock distinguishes true-empty, partial, unavailable, and rate-limited feeds without raw failures', () => {
  const response = {
    ok: true,
    workspace: {
      id: 'workspace-1', title: 'Feed states', automations: [], windows: [], connectors: [], context_sources: [],
    },
  }
  const expected = {
    empty: ['No skills available', 'No access decisions available', 'No recent account activity'],
    partial: [
      'Skill details are unavailable in this partial view',
      'Access details are unavailable in this partial view',
      'Activity details are unavailable in this partial view',
    ],
    unavailable: ['Skill details are unavailable', 'Access details are unavailable', 'Activity details are unavailable'],
    'rate-limited': [
      'Skill details are temporarily rate limited',
      'Access details are temporarily rate limited',
      'Activity details are temporarily rate limited',
    ],
  }
  const cases = [
    {
      state: 'empty',
      supplemental: {
        skills: { ok: true, skills: [] },
        capabilities: { ok: true, capabilities: [] },
        activity: { ok: true, activity: [] },
      },
    },
    {
      state: 'partial',
      supplemental: {
        feedStatus: { state: 'partial', unavailable: ['skills', 'capabilities', 'activity'] },
        raw_error: 'authorization=must-not-render',
      },
    },
    { state: 'unavailable', supplemental: {} },
    {
      state: 'rate-limited',
      supplemental: {
        feedStatus: { state: 'rate-limited', unavailable: ['skills', 'capabilities', 'activity'] },
      },
    },
  ]

  for (const scenario of cases) {
    const dock = inspectionDockModel(workspaceRendererModel(response, scenario.supplemental, 'workspace-1'))
    const emptyCopy = ['skills', 'access', 'activity'].map((id) => dock.tabs.find((tab) => tab.id === id).empty)
    assert.deepEqual(emptyCopy, expected[scenario.state], scenario.state)
    assert.equal(JSON.stringify(dock).includes('authorization'), false)
    assert.equal(JSON.stringify(dock).includes('must-not-render'), false)
  }
})

test('context uses a safe GitHub id fallback and never exposes compiled artifact refs', () => {
  const response = structuredClone(canonical)
  response.workspace.context_sources = [
    { kind: 'artifact', ref: 'runtime/fde-tasks.md', path: 'C:\\private\\fde-tasks.md' },
    { kind: 'github_repository', id: 'ItzJLaugh/Cordia', label: 'Cordia production repository' },
  ]
  const model = workspaceRendererModel(response, {
    artifacts: {
      ok: true,
      artifacts: { 'runtime/fde-tasks.md': '# FDE Mission Brief\nReview the bounded production evidence.' },
    },
  }, 'workspace-1')
  const context = inspectionDockModel(model).tabs.find((tab) => tab.id === 'context')

  assert.deepEqual(context.rows.map((row) => ({ label: row.label, status: row.status })), [
    { label: 'ItzJLaugh/Cordia', status: 'GitHub repository' },
  ])
  const serialized = JSON.stringify({ model, context })
  for (const hidden of ['runtime/fde-tasks.md', 'C:\\private', 'Cordia production repository']) {
    assert.equal(serialized.includes(hidden), false, hidden)
  }
})

test('nonempty unrenderable context reports unavailable instead of claiming it is empty', () => {
  const response = structuredClone(canonical)
  response.workspace.context_sources = [
    { kind: 'artifact', ref: 'runtime/fde-tasks.md' },
    { kind: 'github_repository', id: 'C:\\private\\Cordia', label: 'Friendly repository' },
    { kind: 'github_repository', id: 'token:secret', label: '/home/cordia/private' },
  ]
  const model = workspaceRendererModel(response, {}, 'workspace-1')
  const context = inspectionDockModel(model).tabs.find((tab) => tab.id === 'context')

  assert.deepEqual(context.rows, [])
  assert.equal(context.empty, 'Context details are unavailable')
  const serialized = JSON.stringify({ model, context })
  for (const hidden of ['runtime/fde-tasks.md', 'C:\\private', 'token:secret', '/home/cordia/private']) {
    assert.equal(serialized.includes(hidden), false, hidden)
  }
})

test('InspectionDock renders accessible read-only tabs with exactly one visible panel', async () => {
  const model = inspectionDockModel(workspaceRendererModel(canonical, supplemental, 'workspace-1'))
  const renderer = await render(InspectionDock, { model })
  try {
    const tablist = renderer.root.findByProps({ role: 'tablist' })
    assert.equal(tablist.props['aria-label'], 'Workspace inspection')
    const tabs = renderer.root.findAllByProps({ role: 'tab' })
    assert.equal(tabs.length, 6)
    assert.equal(tabs[0].props['aria-selected'], true)
    assert.equal(tabs[0].props.tabIndex, 0)
    assert.equal(tabs[1].props['aria-selected'], false)
    assert.equal(tabs[1].props.tabIndex, -1)
    assert.equal(renderer.root.findAllByProps({ role: 'tabpanel' }).length, 1)
    assert.equal(renderer.root.findAllByProps({ className: 'inspection-action' }).length, 0)

    await act(async () => { tabs[4].props.onClick() })
    const selected = renderer.root.findAllByProps({ role: 'tab' })
      .find((tab) => tab.props['aria-selected'] === true)
    assert.equal(selected.children.join(''), 'Automations')
    const panel = renderer.root.findByProps({ role: 'tabpanel' })
    assert.equal(panel.props.id, 'inspection-panel-automations')
    assert.equal(panel.findByProps({ className: 'inspection-empty' }).children.join(''), 'No automations configured')
  } finally {
    await act(async () => { renderer.unmount() })
  }
})

test('InspectionDock keyboard navigation wraps and never creates execution controls', async () => {
  const model = inspectionDockModel(workspaceRendererModel(canonical, supplemental, 'workspace-1'))
  const renderer = await render(InspectionDock, { model })
  try {
    let tabs = renderer.root.findAllByProps({ role: 'tab' })
    await act(async () => { tabs[0].props.onKeyDown({ key: 'ArrowLeft', preventDefault() {} }) })
    tabs = renderer.root.findAllByProps({ role: 'tab' })
    assert.equal(tabs[5].props['aria-selected'], true)
    await act(async () => { tabs[5].props.onKeyDown({ key: 'Home', preventDefault() {} }) })
    tabs = renderer.root.findAllByProps({ role: 'tab' })
    assert.equal(tabs[0].props['aria-selected'], true)
    assert.equal(renderer.root.findAllByType('button').length, 6)
  } finally {
    await act(async () => { renderer.unmount() })
  }
})

test('Workspace keeps the dock below the scrollable artifact canvas and out of Alidora', async () => {
  const source = await readFile(new URL('../src/WorkspaceView.jsx', import.meta.url), 'utf8')
  const workspaceStart = source.indexOf('function WorkspaceCanvas(')
  const alidoraStart = source.indexOf('function AlidoraCanvas(')
  const workspaceSource = source.slice(workspaceStart, alidoraStart)
  const alidoraSource = source.slice(alidoraStart)

  assert.match(workspaceSource, /className="workspace-primary"/)
  const canvasEnd = workspaceSource.indexOf('</section>')
  const dockPosition = workspaceSource.indexOf('<InspectionDock model={inspectionDockModel(state.model)} />')
  assert.ok(canvasEnd > 0 && dockPosition > canvasEnd, 'dock must be a sibling below the artifact canvas')
  assert.equal(alidoraSource.includes('<InspectionDock'), false)
  assert.match(source, /state\.model\.cards\.map\(\(card\) =>/,
    'existing artifact cards, including skill actions, must remain on the primary canvas')
})
