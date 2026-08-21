(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.CordiaProfileEntry = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
  function safeWorkspaceHref(workspaceId) {
    const navigation = root.CordiaWorkspaceNavigation;
    const item = navigation && typeof navigation.buildWorkspaceNavigation === 'function'
      ? navigation.buildWorkspaceNavigation(workspaceId)
      : null;
    return item && typeof item.href === 'string' ? item.href : null;
  }

  function safeSurveyHref(value) {
    if (typeof value !== 'string') return null;
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || url.hostname !== 'cordia-survey1.vercel.app' ||
          url.pathname !== '/survey' || url.username || url.password ||
          url.port || url.hash || !url.searchParams.get('state') ||
          url.searchParams.getAll('state').length !== 1) return null;
      return url.toString();
    } catch (_) {
      return null;
    }
  }

  async function resolveCordiaEntry({ getJson, postJson, locationSearch }) {
    const query = new URLSearchParams(locationSearch);
    if (query.has('state') || query.has('result_id')) {
      const states = query.getAll('state');
      const resultIds = query.getAll('result_id');
      if (states.length !== 1 || resultIds.length !== 1 ||
          !states[0].trim() || !resultIds[0].trim()) return '/';
      const completed = await postJson('/surveyor/profile-calibration/complete', {
        state: states[0], result_id: resultIds[0],
      });
      return safeWorkspaceHref(completed && completed.workspace_id) || '/';
    }
    const entry = await getJson('/surveyor/profile-calibration');
    if (entry && entry.calibrated) return safeWorkspaceHref(entry.workspace_id) || '/';
    return safeSurveyHref(entry && entry.survey_url) || '/';
  }

  return { resolveCordiaEntry, safeSurveyHref, safeWorkspaceHref };
}));
