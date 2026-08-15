# Renderer Path-Prefix Hardening Plan

**Goal:** Close the final renderer privacy gap found after the Cordia + Mason integration fix review: metadata-prefixed local paths must never survive into workspace or Alidora renderer models.

**Architecture:** `dashboard-app/src/identifier.js` remains the single sensitive-text boundary. All existing workspace, artifact, graph, skill, and navigation adapters continue consuming that contract. No backend, routing, state, execution, permission, connector, or UI feature change is authorized.

## Task 1

- Add RED regressions for `path:C:\private`, `path:C:private`, `path:/home/cordia/private`, `file:///home/cordia/private`, prefixed UNC paths, and equivalent values embedded in workspace title/description, window title, agent body, workflow identifiers, and Alidora node text.
- Make local-path detection independent of metadata prefixes while preserving normal prose and valid synthetic identifiers.
- Keep credential detection and all previously safe URLs/labels unchanged. The fixed `/github.html` artifact link is not renderer text input and must continue to work.
- Run focused dashboard privacy tests, full dashboard/desktop/backend suites, Vite build, syntax/diff/privacy scans, rebuild committed assets/provenance, and the HEAD-bound clean rebuild verifier.
- Commit source, tests, plan, index, hashes, and provenance together; independently review the scoped change before release.
