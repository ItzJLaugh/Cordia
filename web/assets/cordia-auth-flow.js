(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.CordiaAuthFlow = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function nextStepForResponse(mode, response) {
    if (response.token) return 'session';
    if (mode === 'signup' && !response.dev_code) return 'signup-inbox';
    return 'verification-code';
  }

  function showSignupInbox(view) {
    view.codeField.style.display = 'none';
    view.nextStep.style.display = 'block';
    view.submitButton.style.display = 'none';
    view.note.textContent = 'Check your email for next steps. New account emails contain a verification code; existing account emails tell you to sign in instead.';
  }

  function showSignupCode(view) {
    view.nextStep.style.display = 'none';
    view.codeField.style.display = 'block';
    view.submitButton.style.display = 'block';
    view.submitButton.textContent = 'Verify new account';
    view.codeInput.focus();
  }

  return { nextStepForResponse, showSignupInbox, showSignupCode };
}));
