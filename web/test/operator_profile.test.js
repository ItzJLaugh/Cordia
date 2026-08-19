const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const navigation = require('../assets/workspace-navigation')
const { buildOperatorProfileModel, isSensitiveText } = require('../assets/operator-profile')

function profile(overrides = {}) {
  return {
    title: 'What Cordia currently understands',
    identifiers: [{
      name: 'Evidence-minded',
      meaning: 'You want important claims grounded in sources.',
      use_ai_this_way: 'Ask Cordia to show its evidence.',
      evidence_strength: 'clear',
      criterion: 'must-not-render',
    }],
    understanding: [{ label: 'Current goal', value: 'Prepare useful reports' }],
    evidence: [{ summary: 'I review client-facing claims.', evidence_strength: 'emerging' }],
    connectors: [{
      id: 'github', name: 'GitHub', status: 'Confirmed by user', implementation_status: 'live',
    }],
    still_learning: ['Which systems should be connected'],
    next_action: { type: 'create_interface', label: 'Build my workspace', reason: 'Ready.' },
    latest_workspace: null,
    raw_artifacts: { secret: 'must-not-render' },
    ...overrides,
  }
}

function element() {
  const item = {
    classList: { add() {}, remove() {}, toggle() {} },
    dataset: {},
    disabled: false,
    innerHTML: '',
    listeners: {},
    style: {},
    value: '',
    addEventListener(name, handler) { this.listeners[name] = handler },
    querySelector(selector) {
      if (selector === '[data-generate-workspace]' &&
          this.innerHTML.includes('data-generate-workspace')) {
        if (!this.generateButton) this.generateButton = element()
        return this.generateButton
      }
      if (selector === '[data-generation-status]' &&
          this.innerHTML.includes('data-generation-status')) {
        if (!this.generationStatus) this.generationStatus = element()
        return this.generationStatus
      }
      return null
    },
  }
  return item
}

async function runProfilePage(operatorPayload, generationOptions = {}) {
  const webRoot = path.resolve(__dirname, '..')
  const html = fs.readFileSync(path.join(webRoot, 'profile.html'), 'utf8')
  const inline = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1]
  const elements = new Map()
  const events = new Map()
  const requests = []
  const generationCalls = []
  const replacements = []
  const document = {
    addEventListener(name, handler) { events.set(name, handler) },
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, element())
      return elements.get(id)
    },
    querySelectorAll() { return [] },
  }
  const context = {
    console,
    CordiaOperatorProfile: { buildOperatorProfileModel },
    CordiaWorkspaceGeneration: {
      generate: async (options) => {
        generationCalls.push(options)
        return generationOptions.promise
          ? generationOptions.promise
          : { id: 'workspace-1', href: '/dashboard/?workspace=workspace-1', created: true }
      },
    },
    CordiaWorkspaceNavigation: navigation,
    document,
    fetch: async (url) => {
      requests.push(String(url))
      if (String(url).endsWith('/account/profile')) {
        return { status: 200, json: async () => ({ ok: true, email: 'owner@example.test' }) }
      }
      return { status: 200, json: async () => operatorPayload }
    },
    location: { hostname: 'cordia.example.test', replace(href) { replacements.push(href) } },
  }
  context.window = context
  vm.createContext(context)
  vm.runInContext(inline, context, { filename: 'web/profile.html' })
  await new Promise((resolve) => setImmediate(resolve))
  await new Promise((resolve) => setImmediate(resolve))
  return { ai: document.getElementById('aiProfile'), events, generationCalls, replacements, requests }
}

test('safe latest workspace becomes the primary fixed dashboard action', () => {
  const model = buildOperatorProfileModel({
    ok: true,
    operator_profile: profile({
      latest_workspace: { id: 'workspace-1', name: 'Inspection workspace', definition: 'private' },
      next_action: { type: 'refine_profile', label: 'Refine my profile', reason: 'Add more detail.' },
    }),
  }, navigation)

  assert.equal(model.state, 'ready')
  assert.deepEqual(model.primaryAction, {
    kind: 'link', label: 'Open Inspection workspace', href: '/dashboard/?workspace=workspace-1',
  })
  assert.deepEqual(model.secondaryAction, { kind: 'surveyor', label: 'Refine with Surveyor' })
  assert.deepEqual(Object.keys(model.identifiers[0]).sort(), [
    'evidenceStrength', 'meaning', 'name', 'useAiThisWay',
  ])
  assert.doesNotMatch(JSON.stringify(model), /criterion|raw_artifacts|must-not-render/)
})

test('unsafe latest workspace fails closed without scanning or creating a forged href', () => {
  const model = buildOperatorProfileModel({
    ok: true,
    operator_profile: profile({
      latest_workspace: { id: 'github_pat_abcdefghijklmnopqrstuvwxyz012345', name: 'Unsafe' },
      next_action: { type: 'create_interface', label: 'Build my workspace', reason: 'Ready.' },
    }),
  }, navigation)

  assert.deepEqual(model.primaryAction, {
    kind: 'generate', label: 'Build my workspace',
  })
  assert.doesNotMatch(JSON.stringify(model), /github_pat_/)
  assert.doesNotMatch(JSON.stringify(model), /builder\.html/)
})

test('incomplete profile resolves to a Surveyor control instead of a server supplied URL', () => {
  const model = buildOperatorProfileModel({
    ok: true,
    operator_profile: profile({
      next_action: {
        type: 'refine_profile',
        label: 'Refine my profile',
        reason: 'Cordia has part of your picture.',
        href: 'https://attacker.example/',
      },
    }),
  }, navigation)

  assert.deepEqual(model.primaryAction, { kind: 'surveyor', label: 'Refine my profile' })
  assert.equal(model.secondaryAction, null)
  assert.doesNotMatch(JSON.stringify(model), /attacker/)
})

test('malformed and sensitive projection text produces bounded visible recovery', () => {
  for (const payload of [
    null,
    { ok: false, error: 'database path C:\\private\\data' },
    { ok: true, operator_profile: { title: 'token=private-value' } },
  ]) {
    const model = buildOperatorProfileModel(payload, navigation)
    assert.deepEqual(model, {
      state: 'error',
      message: 'Cordia could not load this profile safely. Try again.',
    })
  }
})

test('common local paths and private key headers never enter the render model', () => {
  for (const value of [
    '/tmp',
    './private/key.txt',
    '..\\private\\key.txt',
    '-----BEGIN RSA PRIVATE KEY-----',
  ]) {
    assert.equal(isSensitiveText(value), true, value)
    const model = buildOperatorProfileModel({
      ok: true,
      operator_profile: profile({ evidence: [{ summary: value, evidence_strength: 'clear' }] }),
    }, navigation)
    assert.equal(model.state, 'ready')
    assert.deepEqual(model.evidence, [])
  }
})

test('safe remote URLs remain visible while nested local paths are rejected', () => {
  for (const value of [
    'See https://example.test/tmp for public docs.',
    'See https://[2001:db8::1]/docs/start.',
  ]) assert.equal(isSensitiveText(value), false, value)

  assert.equal(isSensitiveText('See https://example.test/docs?next=/tmp.'), true)
})

test('the account assessment entry targets the operator profile and legacy page is certification-specific', () => {
  const webRoot = path.resolve(__dirname, '..')
  const shell = fs.readFileSync(path.join(webRoot, 'assets', 'cordia-shell.js'), 'utf8')
  const legacy = fs.readFileSync(path.join(webRoot, 'assessment.html'), 'utf8')
  const page = fs.readFileSync(path.join(webRoot, 'profile.html'), 'utf8')
  const surveyor = fs.readFileSync(path.join(webRoot, 'assets', 'cordia-surveyor.js'), 'utf8')

  assert.match(shell, /\['Assessment', 'profile\.html#aiSection'/)
  assert.match(legacy, /Certification assessment/i)
  assert.match(page, /surveyor\/operator-profile/)
  assert.doesNotMatch(page, /surveyor\/artifacts/)
  assert.match(page, /cordia:profile-updated/)
  assert.match(shell, /cordia-surveyor-flow\.js/)
  assert.match(surveyor, /setProgress\(r\.data\)/)
  assert.doesNotMatch(surveyor, /profile\.complete === true/)
  assert.doesNotMatch(surveyor, /percent_complete/)
})

test('profile page renders the canonical open action and refreshes after Surveyor updates', async () => {
  const payload = {
    ok: true,
    operator_profile: profile({ latest_workspace: { id: 'workspace-1', name: 'Inspection workspace' } }),
  }
  const rendered = await runProfilePage(payload)

  assert.match(rendered.ai.innerHTML, /What Cordia is still learning/)
  assert.match(rendered.ai.innerHTML, /Open Inspection workspace/)
  assert.match(rendered.ai.innerHTML, /\/dashboard\/\?workspace=workspace-1/)
  assert.equal(rendered.requests.filter((url) => url.endsWith('/surveyor/operator-profile')).length, 1)

  rendered.events.get('cordia:profile-updated')()
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(rendered.requests.filter((url) => url.endsWith('/surveyor/operator-profile')).length, 2)
})

test('profile page shows bounded recovery for a malformed operator projection', async () => {
  const rendered = await runProfilePage({ ok: false, error: 'C:\\private\\database' })

  assert.match(rendered.ai.innerHTML, /could not load this profile safely/i)
  assert.doesNotMatch(rendered.ai.innerHTML, /private|database/i)
})

test('profile page renders one fixed generation action and suppresses duplicate clicks', async () => {
  let resolveGeneration
  const promise = new Promise((resolve) => { resolveGeneration = resolve })
  const rendered = await runProfilePage({
    ok: true,
    operator_profile: profile(),
  }, { promise })
  const button = rendered.ai.querySelector('[data-generate-workspace]')

  assert.ok(button)
  button.listeners.click()
  button.listeners.click()
  assert.equal(rendered.generationCalls.length, 1)
  assert.equal(button.disabled, true)
  assert.equal(button.textContent, 'Cordia is building your workspace…')

  resolveGeneration({ id: 'workspace-1', href: '/dashboard/?workspace=workspace-1', created: true })
  await new Promise((resolve) => setImmediate(resolve))
  assert.deepEqual(rendered.replacements, ['/dashboard/?workspace=workspace-1'])
})

test('profile page restores the generation control and shows only fixed recovery copy', async () => {
  let rejectGeneration
  const promise = new Promise((_resolve, reject) => { rejectGeneration = reject })
  const rendered = await runProfilePage({
    ok: true,
    operator_profile: profile(),
  }, { promise })
  const button = rendered.ai.querySelector('[data-generate-workspace]')

  const click = button.listeners.click()
  rejectGeneration(new Error('token=PRIVATE C:\\private\\workspace'))
  await click

  const status = rendered.ai.querySelector('[data-generation-status]')
  assert.equal(button.disabled, false)
  assert.equal(button.textContent, 'Build my workspace')
  assert.equal(status.textContent, 'Cordia could not build your workspace. Try again.')
  assert.doesNotMatch(status.textContent, /PRIVATE|token=|private\\workspace/)
})
