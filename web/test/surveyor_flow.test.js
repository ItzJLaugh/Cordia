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


async function runRejectedDraft() {
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
  const context = {
    CordiaSurveyorFlow: flow,
    CustomEvent: function CustomEvent(name, options) { this.name = name; this.detail = options && options.detail },
    console,
    document,
    fetch: async (url) => {
      requests.push(String(url))
      if (String(url).endsWith('/auth/session')) return { ok: true }
      if (String(url).endsWith('/surveyor/conversation')) {
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
