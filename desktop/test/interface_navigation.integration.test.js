const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const repoRoot = path.resolve(__dirname, '..', '..');
const interfacePath = path.join(repoRoot, 'web', 'interface.html');

function element(tagName, attributes = {}, textContent = '') {
  return {
    tagName,
    attributes: { ...attributes },
    children: [],
    textContent,
    className: attributes.class || '',
    dataset: Object.fromEntries(Object.entries(attributes)
      .filter(([name]) => name.startsWith('data-'))
      .map(([name, value]) => [name.slice(5), value])),
    setAttribute(name, value) { this.attributes[name] = String(value); },
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
    addEventListener() {},
    querySelectorAll() { return []; },
    insertAdjacentHTML() {},
  };
}

function pageDocument(html) {
  const elements = new Map();
  const tags = /<([A-Za-z][\w-]*)([^>]*\sid="([^"]+)"[^>]*)>([^<]*)/g;
  for (const match of html.matchAll(tags)) {
    const attributes = Object.fromEntries(
      [...match[2].matchAll(/([:\w-]+)(?:="([^"]*)")?/g)]
        .map(([, name, value]) => [name, value === undefined ? '' : value]),
    );
    elements.set(match[3], element(match[1], attributes, match[4].trim()));
  }
  return {
    getElementById(id) { return elements.get(id) || null; },
    createElement(tagName) { return element(tagName); },
  };
}

async function renderWorkspacePage(workspace) {
  const html = fs.readFileSync(interfacePath, 'utf8');
  const document = pageDocument(html);
  const context = {
    document,
    location: { hostname: 'cordia.example.test', search: '?id=w-1_A.2' },
    URLSearchParams,
    console,
    fetch: async (url) => ({
      status: 200,
      json: async () => String(url).startsWith('/surveyor/workspace?')
        ? { workspace }
        : {},
    }),
  };
  context.window = context;
  vm.createContext(context);

  for (const [, source] of html.matchAll(/<script[^>]*\ssrc="([^"]+)"[^>]*><\/script>/g)) {
    if (!source.startsWith('assets/workspace-navigation.js')) continue;
    var scriptPath = source.split('?', 1)[0];
    vm.runInContext(fs.readFileSync(path.join(repoRoot, 'web', scriptPath), 'utf8'), context, { filename: source });
  }
  const inlineScripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  vm.runInContext(inlineScripts.at(-1)[1], context, { filename: 'web/interface.html' });
  await new Promise((resolve) => setImmediate(resolve));

  return document;
}

test('actual workspace page keeps Cordia primary and renders the authenticated Alidora destination', async () => {
  const document = await renderWorkspacePage({ id: 'w-1_A.2', title: 'Launch', agents: [] });
  const primary = document.getElementById('cordiaAgentPanel');
  const label = document.getElementById('cordiaAgentLabel');
  const navigation = document.getElementById('alidoraNav');

  assert.equal(primary.tagName, 'section');
  assert.equal(primary.attributes['data-surface'], 'primary');
  assert.equal(label.textContent, 'Cordia Agent');
  assert.equal(navigation.children.length, 1);
  assert.equal(navigation.children[0].attributes.href, 'dashboard/?workspace=w-1_A.2');
  assert.equal(navigation.children[0].attributes['data-surface'], 'non-primary');
});

test('actual workspace page renders no Alidora link for a hostile authenticated workspace id', async () => {
  const document = await renderWorkspacePage({ id: 'C:\\private\\workspace', title: 'Launch', agents: [] });

  assert.deepEqual(document.getElementById('alidoraNav').children, []);
});
