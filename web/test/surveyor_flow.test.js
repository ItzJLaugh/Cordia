const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const flow = require('../assets/cordia-surveyor-flow')


test('projects bounded progress and a fixed assessment completion action', () => {
  assert.deepEqual(flow.model({
    ok: true,
    onboarding: {
      turn_limit: 12,
      turns_used: 9,
      turns_remaining: 3,
      complete: false,
    },
  }), {
    state: 'ready',
    turnLimit: 12,
    turnsUsed: 9,
    turnsRemaining: 3,
    complete: false,
  })
  assert.equal(flow.completionDestination(), 'profile.html#aiSection')
})


test('fails closed for inconsistent progress', () => {
  for (const payload of [
    null,
    { ok: true, onboarding: {
      turn_limit: 12, turns_used: 13, turns_remaining: -1, complete: true,
    } },
    { ok: true, onboarding: {
      turn_limit: '12', turns_used: 0, turns_remaining: 12, complete: false,
    } },
    { ok: true, onboarding: {
      turn_limit: 12, turns_used: 7, turns_remaining: 6, complete: false,
    } },
  ]) assert.deepEqual(flow.model(payload), { state: 'error' })
})


test('classifies a failed submission only from canonical persisted progress', () => {
  const payload = (turnsUsed) => ({
    ok: true,
    onboarding: {
      turn_limit: 12,
      turns_used: turnsUsed,
      turns_remaining: 12 - turnsUsed,
      complete: turnsUsed === 12,
    },
  })

  assert.equal(flow.reconcileSubmission(3, payload(4)).state, 'saved')
  assert.equal(flow.reconcileSubmission(3, payload(3)).state, 'retry')
  assert.equal(flow.reconcileSubmission(3, payload(5)).state, 'unknown')
  assert.equal(flow.reconcileSubmission(12, payload(12)).state, 'unknown')
  assert.equal(flow.reconcileSubmission(3, { ok: false }).state, 'unknown')
})


test('Surveyor source has no builder or certification destination', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '..', 'assets', 'cordia-surveyor.js'), 'utf8'
  )
  assert.doesNotMatch(source, /builder\.html|certifications\.html|assessment\.html/i)
  assert.match(source, /data-act="assessment"/)
  assert.match(source, /Question.*of.*12/)
})


function makeElement(tag = 'div') {
  const item = {
    tagName: tag.toUpperCase(),
    children: [],
    className: '',
    dataset: {},
    disabled: false,
    hidden: false,
    id: '',
    listeners: {},
    scrollHeight: 40,
    scrollTop: 0,
    style: {},
    value: '',
    _innerHTML: '',
    addEventListener(name, handler) { this.listeners[name] = handler },
    appendChild(child) { child.parentNode = this; this.children.push(child); return child },
    closest(selector) {
      return selector === '.sv-act' && this.className === 'sv-act' ? this : null
    },
    focus() {},
    querySelector(selector) {
      if (this._known && this._known[selector]) return this._known[selector]
      const wantedId = selector.startsWith('#') ? selector.slice(1) : null
      const wantedClass = selector.startsWith('.') ? selector.slice(1) : null
      return this.children.find((child) => (
        (wantedId && child.id === wantedId) ||
        (wantedClass && String(child.className).split(' ').includes(wantedClass))
      )) || null
    },
    remove() {
      if (!this.parentNode) return
      this.parentNode.children = this.parentNode.children.filter((child) => child !== this)
    },
    setAttribute(name, value) {
      if (name === 'id') this.id = value
      else if (name.startsWith('data-')) this.dataset[name.slice(5)] = value
      else this[name] = value
    },
  }
  Object.defineProperty(item, 'childElementCount', {
    get() { return item.children.length },
  })
  Object.defineProperty(item, 'innerHTML', {
    get() { return item._innerHTML },
    set(value) {
      item._innerHTML = String(value)
      item.children = []
      if (!String(value).includes('class="sv-win"')) return
      const body = makeElement('div')
      body.id = 'svBody'
      const input = makeElement('textarea')
      input.id = 'svInput'
      const send = makeElement('button')
      send.id = 'svSend'
      const state = makeElement('div')
      state.id = 'svState'
      const progress = makeElement('div')
      progress.id = 'svProgress'
      const close = makeElement('button')
      close.id = 'svClose'
      const actions = makeElement('div')
      actions.className = 'sv-acts'
      item._known = {
        '#svBody': body,
        '#svInput': input,
        '#svSend': send,
        '#svState': state,
        '#svProgress': progress,
        '#svClose': close,
        '.sv-acts': actions,
      }
    },
  })
  return item
}


async function runRejectedDraft(mode = 'not-saved') {
  const source = fs.readFileSync(
    path.resolve(__dirname, '..', 'assets', 'cordia-surveyor.js'), 'utf8'
  )
  const documentEvents = new Map()
  const document = {
    body: makeElement('body'),
    documentElement: { style: {} },
    head: makeElement('head'),
    addEventListener(name, handler) { documentEvents.set(name, handler) },
    createElement(tag) { return makeElement(tag) },
    dispatchEvent() {},
  }
  const requests = []
  let conversationReads = 0
  const context = {
    CordiaSurveyorFlow: flow,
    CustomEvent: function CustomEvent(name, options) { this.name = name; this.detail = options && options.detail },
    console,
    document,
    fetch: async (url) => {
      requests.push(String(url))
      if (String(url).endsWith('/auth/session')) return { ok: true }
      if (String(url).endsWith('/surveyor/conversation')) {
        conversationReads += 1
        if (mode === 'unknown' && conversationReads > 1) {
          throw new Error('ambiguous transport failure')
        }
        if (mode === 'committed' && conversationReads > 1) {
          return {
            status: 200,
            json: async () => ({
              ok: true,
              messages: [
                { role: 'assistant', content: 'Welcome and first prompt.' },
                { role: 'user', content: 'My original draft' },
                { role: 'assistant', content: 'Canonical next prompt.' },
              ],
              key: 'role_tendency',
              options: [{ value: 'prototyper', label: 'A builder' }],
              onboarding: {
                turn_limit: 12, turns_used: 1, turns_remaining: 11, complete: false,
              },
            }),
          }
        }
        return {
          status: 200,
          json: async () => ({
            ok: true,
            messages: [],
            key: 'domain',
            options: [],
            onboarding: {
              turn_limit: 12, turns_used: 0, turns_remaining: 12, complete: false,
            },
          }),
        }
      }
      if (String(url).endsWith('/surveyor/profile')) {
        return { status: 200, json: async () => ({ ok: true, llm: { live: true } }) }
      }
      return {
        status: 500,
        json: async () => ({
          ok: false,
          error: 'token=github_pat_PRIVATE C:\\private\\workspace',
        }),
      }
    },
    location: { hostname: 'cordia.example.test', href: '' },
    requestAnimationFrame(callback) { callback() },
    setTimeout(callback) { callback() },
    addEventListener() {},
  }
  context.window = context
  vm.createContext(context)
  vm.runInContext(source, context, { filename: 'cordia-surveyor.js' })
  await context.Cordia.surveyor.open()
  await new Promise((resolve) => setImmediate(resolve))
  await new Promise((resolve) => setImmediate(resolve))

  const root = document.body.children.at(-1)
  const input = root.querySelector('#svInput')
  input.value = 'My original draft'
  root.querySelector('#svSend').listeners.click()
  await new Promise((resolve) => setImmediate(resolve))
  await new Promise((resolve) => setImmediate(resolve))

  return { input, root, requests }
}


test('rejected submit restores the draft and renders only fixed recovery copy', async () => {
  const page = await runRejectedDraft()
  const body = page.root.querySelector('#svBody')
  const rendered = body.children.map((item) => item.innerHTML).join(' ')

  assert.equal(page.input.value, 'My original draft')
  assert.equal(page.root.querySelector('#svProgress').textContent, 'Question 1 of 12')
  assert.match(rendered, /Cordia could not save that answer\. Your draft is still here — try again\./)
  assert.doesNotMatch(rendered, /github_pat_PRIVATE|private\\workspace|token=/)
})


test('response loss after commit reconciles canonical progress without resubmitting the draft', async () => {
  const page = await runRejectedDraft('committed')
  const body = page.root.querySelector('#svBody')
  const rendered = body.children.map((item) => item.innerHTML).join(' ')

  assert.equal(page.input.value, '')
  assert.equal(page.root.querySelector('#svProgress').textContent, 'Question 2 of 12')
  assert.match(rendered, /Canonical next prompt/)
  assert.doesNotMatch(rendered, /could not save that answer|try again/i)
  assert.equal(page.requests.filter((url) => url.endsWith('/surveyor/message')).length, 1)
  assert.equal(body.children.filter((item) => item.dataset.who === 'user').length, 1)
})


test('ambiguous reconciliation keeps the draft but locks retry until reload', async () => {
  const page = await runRejectedDraft('unknown')
  const body = page.root.querySelector('#svBody')
  const rendered = body.children.map((item) => item.innerHTML).join(' ')

  assert.equal(page.input.value, 'My original draft')
  assert.equal(page.root.querySelector('#svSend').disabled, true)
  assert.match(rendered, /Reload Surveyor before trying again/)
})
