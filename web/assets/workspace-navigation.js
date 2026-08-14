/* Safe Cordia workspace navigation shared by the vanilla workspace surface. */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.CordiaWorkspaceNavigation = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';

  // Matches the opaque identifier contract enforced by the Alidora backend map.
  var SAFE_WORKSPACE_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/;
  var CREDENTIAL_SHAPED_ID = /^(?:(?:sk|pk|rk)-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|github_pat_[A-Za-z0-9_]{20,}|(?:api[-_.]?key|access[-_.]?token|token|secret|password|credential)[-_.])/i;

  function buildAlidoraNavigation(workspaceId) {
    if (typeof workspaceId !== 'string' || !SAFE_WORKSPACE_ID.test(workspaceId) ||
        CREDENTIAL_SHAPED_ID.test(workspaceId)) return null;
    return {
      primarySurface: 'Cordia Agent',
      navigation: {
        label: 'Alidora',
        subtitle: 'Agentic System Builder',
        href: 'dashboard/?workspace=' + encodeURIComponent(workspaceId),
      },
    };
  }

  function renderAlidoraNavigation(host, workspaceId, document) {
    var model = buildAlidoraNavigation(workspaceId);
    host.replaceChildren();
    if (!model) return null;

    var link = document.createElement('a');
    link.className = 'alidora-nav';
    link.setAttribute('href', model.navigation.href);
    link.setAttribute('data-surface', 'non-primary');
    link.setAttribute('aria-label', 'Open Alidora Agentic System Builder');
    var label = document.createElement('strong');
    label.textContent = model.navigation.label;
    var subtitle = document.createElement('small');
    subtitle.textContent = model.navigation.subtitle;
    link.append(label, subtitle);
    host.append(link);
    return model;
  }

  return {
    buildAlidoraNavigation: buildAlidoraNavigation,
    renderAlidoraNavigation: renderAlidoraNavigation,
  };
});
