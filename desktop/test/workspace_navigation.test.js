const assert = require('node:assert/strict');
const test = require('node:test');

const {
  buildAlidoraNavigation,
  renderAlidoraNavigation,
} = require('../../web/assets/workspace-navigation.js');

function element(tagName) {
  return {
    tagName,
    attributes: {},
    children: [],
    textContent: '',
    setAttribute(name, value) { this.attributes[name] = value; },
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
  };
}

test('renders a non-primary Alidora link for one safe authenticated workspace id', () => {
  const host = element('nav');
  const document = { createElement: element };

  const model = renderAlidoraNavigation(host, 'w-1_A.2', document);

  assert.deepEqual(model, {
    primarySurface: 'Cordia Agent',
    navigation: {
      label: 'Alidora',
      subtitle: 'Agentic System Builder',
      href: 'dashboard/?workspace=w-1_A.2',
    },
  });
  assert.equal(host.children.length, 1);
  assert.equal(host.children[0].tagName, 'a');
  assert.equal(host.children[0].attributes.href, 'dashboard/?workspace=w-1_A.2');
  assert.equal(host.children[0].attributes['data-surface'], 'non-primary');
  assert.equal(host.children[0].children[0].textContent, 'Alidora');
  assert.equal(host.children[0].children[1].textContent, 'Agentic System Builder');
});

test('does not construct or render a link for unsafe workspace ids', () => {
  const hostileIds = [
    'C:\\private\\workspace',
    '/home/cordia/private',
    'sk-abcdefghijk',
    'ghp_abcdefghijklmnopqrstuvwxyz',
    'github_pat_abcdefghijklmnopqrstuvwxyz0123456789',
    'api_key=must-not-leak',
    'w-1&workspace=someone-else',
    'profile: raw artifact text',
    '',
  ];

  hostileIds.forEach((workspaceId) => {
    const host = element('nav');
    const document = { createElement: element };

    assert.equal(buildAlidoraNavigation(workspaceId), null, workspaceId);
    assert.equal(renderAlidoraNavigation(host, workspaceId, document), null, workspaceId);
    assert.deepEqual(host.children, [], workspaceId);
  });
});
