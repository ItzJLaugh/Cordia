(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.CordiaAuthFlow = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
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

  async function resumeAuthenticatedWorkspace(options) {
    const fallback = 'surveyor.html';
    let destination = fallback;
    try {
      const response = await options.fetch(
        options.apiBase + '/surveyor/interfaces',
        { method: 'GET', credentials: 'same-origin' },
      );
      if (response && response.ok && typeof response.json === 'function') {
        const payload = await response.json();
        const first = payload && Array.isArray(payload.interfaces)
          ? payload.interfaces[0]
          : null;
        const navigation = root.CordiaWorkspaceNavigation;
        const workspace = navigation && typeof navigation.buildWorkspaceNavigation === 'function'
          ? navigation.buildWorkspaceNavigation(first && first.id)
          : null;
        if (workspace && typeof workspace.href === 'string') destination = workspace.href;
      }
    } catch (_) {
      // Interface read failures intentionally use the fixed safe entry.
    }
    if (options && typeof options.navigate === 'function') options.navigate(destination);
    return destination;
  }

  return { nextStepForResponse, resumeAuthenticatedWorkspace, showSignupInbox, showSignupCode };
}));
