const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const repoRoot = path.resolve(__dirname, '..', '..');
const webRoot = path.join(repoRoot, 'web');

function inlineScript(html) {
  return [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
}

function externalWorkspaceNavigation(html, context) {
  const source = [...html.matchAll(/<script[^>]*\ssrc="([^"]+)"[^>]*><\/script>/g)]
    .map((match) => match[1])
    .find((value) => value.startsWith('assets/workspace-navigation.js'));
  if (!source) return;
  vm.runInContext(
    fs.readFileSync(path.join(webRoot, source.split('?', 1)[0]), 'utf8'),
    context,
    { filename: source },
  );
}

function genericElement() {
  return {
    attributes: {},
    children: [],
    dataset: {},
    disabled: false,
    hidden: false,
    innerHTML: '',
    textContent: '',
    value: '',
    addEventListener(name, handler) { this.listeners ||= {}; this.listeners[name] = handler; },
    appendChild(child) { this.children.push(child); },
    append(...children) { this.children.push(...children); },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    querySelector() { return genericElement(); },
    querySelectorAll() { return []; },
    insertAdjacentHTML() {},
    replaceChildren(...children) { this.children = children; },
  };
}

function documentWithIds() {
  const elements = new Map();
  return {
    elements,
    createElement: genericElement,
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, genericElement());
      return elements.get(id);
    },
  };
}

async function runLegacyEntry(search) {
  const html = fs.readFileSync(path.join(webRoot, 'interface.html'), 'utf8');
  const redirects = [];
  const document = documentWithIds();
  const location = {
    hostname: 'cordia.example.test',
    search,
    replace(destination) { redirects.push(destination); },
  };
  const context = { console, document, fetch: async () => ({ status: 404, json: async () => ({}) }), location, URLSearchParams };
  context.window = context;
  vm.createContext(context);
  externalWorkspaceNavigation(html, context);
  vm.runInContext(inlineScript(html), context, { filename: 'web/interface.html' });
  await new Promise((resolve) => setImmediate(resolve));
  return { html, redirects };
}

async function runWorkspaceList(workspaceId) {
  const html = fs.readFileSync(path.join(webRoot, 'interfaces.html'), 'utf8');
  const document = documentWithIds();
  const context = {
    console,
    Date,
    document,
    fetch: async () => ({
      status: 200,
      json: async () => ({
        interfaces: [{ id: workspaceId, name: 'Launch', definition: {} }],
        defaults: {},
      }),
    }),
    location: { hostname: 'cordia.example.test' },
  };
  context.window = context;
  vm.createContext(context);
  externalWorkspaceNavigation(html, context);
  vm.runInContext(inlineScript(html), context, { filename: 'web/interfaces.html' });
  await new Promise((resolve) => setImmediate(resolve));
  return document.getElementById('content').innerHTML;
}

async function runBuilderSave(workspaceId) {
  const html = fs.readFileSync(path.join(webRoot, 'builder.html'), 'utf8');
  const document = documentWithIds();
  document.getElementById('fName').value = 'Launch';
  document.getElementById('fSurface').value = 'chat';
  const location = { hostname: 'cordia.example.test', search: '', href: '' };
  const context = {
    console,
    document,
    fetch: async (url, options = {}) => ({
      status: 200,
      json: async () => String(url).endsWith('/surveyor/interface') && options.method === 'POST'
        ? { ok: true, id: workspaceId }
        : String(url).endsWith('/surveyor/interfaces')
          ? { defaults: {}, interfaces: [] }
          : {},
    }),
    location,
    setTimeout(callback) { callback(); },
    URLSearchParams,
  };
  context.window = context;
  vm.createContext(context);
  externalWorkspaceNavigation(html, context);
  vm.runInContext(inlineScript(html), context, { filename: 'web/builder.html' });
  await new Promise((resolve) => setImmediate(resolve));
  document.getElementById('saveBtn').listeners.click.call(document.getElementById('saveBtn'));
  await new Promise((resolve) => setImmediate(resolve));
  return location.href;
}

test('legacy bookmarks redirect only a valid id into the primary dashboard route', async () => {
  const workspaceId = '0f1234567890abcdef1234567890abcd';
  const result = await runLegacyEntry(`?id=${workspaceId}&view=alidora&next=%2Fprivate`);

  assert.deepEqual(result.redirects, [`/dashboard/?workspace=${workspaceId}`]);
  assert.equal(result.html.includes('/private'), false);
});

test('legacy bookmarks fail closed to the workspace list for missing path and credential ids', async () => {
  const searches = [
    '',
    '?id=C%3A%5Cprivate%5Cworkspace',
    '?id=%2Fhome%2Fcordia%2Fprivate',
    '?id=token%3Asecret-value',
    '?id=github_pat_abcdefghijklmnopqrstuvwxyz0123456789',
  ];

  for (const search of searches) {
    assert.deepEqual((await runLegacyEntry(search)).redirects, ['/interfaces.html'], search);
  }
});

test('saved workspace list opens the primary dashboard without an Alidora default', async () => {
  const workspaceId = '0f1234567890abcdef1234567890abcd';
  const rendered = await runWorkspaceList(workspaceId);

  assert.match(rendered, new RegExp(`href="/dashboard/\\?workspace=${workspaceId}"`));
  assert.equal(rendered.includes('view=alidora'), false);
  assert.equal(rendered.includes('interface.html?id='), false);
});

test('builder save completion opens the primary dashboard for the returned canonical id', async () => {
  const workspaceId = '0f1234567890abcdef1234567890abcd';

  assert.equal(await runBuilderSave(workspaceId), `/dashboard/?workspace=${workspaceId}`);
});
