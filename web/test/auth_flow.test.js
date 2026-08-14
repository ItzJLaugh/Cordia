const assert = require('node:assert/strict');
const test = require('node:test');

const {
  nextStepForResponse,
  showSignupInbox,
  showSignupCode,
} = require('../assets/cordia-auth-flow');

function element(display = '') {
  return {
    style: { display },
    textContent: '',
    focused: false,
    focus() { this.focused = true; },
  };
}

function fixture() {
  return {
    codeField: element('none'),
    codeInput: element(),
    nextStep: element('none'),
    submitButton: element('block'),
    note: element('none'),
  };
}

test('signup success shows neutral inbox choices without claiming a code arrived', () => {
  const view = fixture();

  showSignupInbox(view);

  assert.equal(view.codeField.style.display, 'none');
  assert.equal(view.codeInput.focused, false);
  assert.equal(view.nextStep.style.display, 'block');
  assert.equal(view.submitButton.style.display, 'none');
  assert.match(view.note.textContent, /check your email for next steps/i);
  assert.doesNotMatch(view.note.textContent, /code (was|has been) sent/i);
});

test('signup code entry appears only after the user says they received a code', () => {
  const view = fixture();
  showSignupInbox(view);

  showSignupCode(view);

  assert.equal(view.nextStep.style.display, 'none');
  assert.equal(view.codeField.style.display, 'block');
  assert.equal(view.submitButton.style.display, 'block');
  assert.equal(view.submitButton.textContent, 'Verify new account');
  assert.equal(view.codeInput.focused, true);
});

test('successful signup and login responses choose different next steps', () => {
  assert.equal(nextStepForResponse('signup', { ok: true }), 'signup-inbox');
  assert.equal(
    nextStepForResponse('signup', { ok: true, dev_code: '482193' }),
    'verification-code',
  );
  assert.equal(nextStepForResponse('login', { ok: true }), 'verification-code');
  assert.equal(
    nextStepForResponse('login', { ok: true, token: 'session-token' }),
    'session',
  );
});
