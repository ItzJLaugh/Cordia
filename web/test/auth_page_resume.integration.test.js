const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const webRoot = path.resolve(__dirname, '..');

function element() {
  return {
    classList: { add() {}, toggle() {} },
    disabled: false,
    innerHTML: '',
    style: {},
    textContent: '',
    value: '',
    focus() {},
  };
}

function storage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) || null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, String(value)),
  };
}

function indexScript() {
  const html = fs.readFileSync(path.join(webRoot, 'index.html'), 'utf8');
  return [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
}

async function runPage({ restored }) {
  const redirects = [];
  const requests = [];
  const elements = new Map();
  const document = { getElementById(id) {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  } };
  const location = {
    hostname: 'cordia.example.test',
    protocol: 'https:',
    replace: (destination) => redirects.push(destination),
  };
  const context = {
    document,
    fetch: async (url, options) => {
      requests.push([url, options]);
      if (String(url).endsWith('/auth/me')) {
        return { json: async () => restored ? { ok: true, user: { email: 'ada@example.test' } } : { ok: false } };
      }
      if (String(url).endsWith('/auth/login')) return { json: async () => ({ ok: true, token: 'legacy-token' }) };
      if (String(url).endsWith('/surveyor/interfaces')) return {
        ok: true,
        json: async () => ({ interfaces: [{ id: 'resume-workspace' }] }),
      };
      throw new Error('unexpected request');
    },
    localStorage: storage(),
    location,
    sessionStorage: storage(),
    setTimeout(callback) { callback(); },
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(webRoot, 'assets/workspace-navigation.js'), 'utf8'), context);
  vm.runInContext(fs.readFileSync(path.join(webRoot, 'assets/cordia-auth-flow.js'), 'utf8'), context);
  const coordinator = context.CordiaAuthFlow.resumeAuthenticatedWorkspace;
  let coordinatorCalls = 0;
  context.CordiaAuthFlow.resumeAuthenticatedWorkspace = (options) => {
    coordinatorCalls += 1;
    return coordinator(options);
  };
  vm.runInContext(indexScript(), context);
  await new Promise((resolve) => setImmediate(resolve));

  if (!restored) {
    document.getElementById('email').value = 'ada@example.test';
    document.getElementById('password').value = 'password123';
    await document.getElementById('authForm').onsubmit({ preventDefault() {} });
  }
  await new Promise((resolve) => setImmediate(resolve));
  return { coordinatorCalls, redirects, requests };
}

for (const [label, restored] of [['cookie restoration', true], ['successful authentication', false]]) {
  test(`${label} resumes through the shared safe workspace coordinator`, async () => {
    const result = await runPage({ restored });

    assert.equal(result.coordinatorCalls, 1);
    assert.deepEqual(result.redirects, ['/dashboard/?workspace=resume-workspace']);
    assert.equal(result.requests.at(-1)[0], 'https://cordia.example.test/surveyor/interfaces');
    assert.equal(result.requests.at(-1)[1].method, 'GET');
    assert.equal(result.requests.at(-1)[1].credentials, 'same-origin');
  });
}
