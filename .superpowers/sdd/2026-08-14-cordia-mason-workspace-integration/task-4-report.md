# Task 4 Report: Discoverable Unified Workspace Production Route

## Status

Complete. The resolved Cordia build worktree now sends normal saved and newly created workspace traffic to the unified dashboard's Workspace view. Alidora is reachable only as an explicit advanced view for the same canonical workspace id. The legacy `interface.html?id=...` route is a fail-closed compatibility redirect.

## TDD evidence

### RED: production workspace entry

Command:

```powershell
Set-Location desktop
node --test test/workspace_navigation.test.js test/workspace_entry.integration.test.js test/alidora_production_target.test.js
```

Observed before production edits: 46 tests ran because the package test glob was also included in the first invocation; 37 passed and 9 failed for the intended missing behavior. Failures showed that:

- `buildWorkspaceNavigation` did not exist.
- Alidora omitted `&view=alidora`.
- `interface.html` did not redirect.
- the saved list still emitted `interface.html?id=...`.
- builder completion still emitted `interface.html?id=...`.
- the committed bundle lacked Workspace-primary contracts.

### GREEN: production workspace entry

Focused routing after implementation, before staging the rebuilt assets: 8 passed and the one remaining failure correctly identified the stale/untracked production bundle. After the Vite build and staging the exact generated files, the focused suite passed 9/9.

### RED/GREEN: actual safe-id grammar

Added drive-relative cases for `C:drive-relative` to the dashboard route and fixed run API tests. The focused dashboard run first failed 2/17 because both paths still admitted the colon. Removing colon from the safe-id grammar made the same focused suite pass 17/17 and aligned it with the backend Alidora identifier contract.

### RED/GREEN: Workspace-primary production title

The production-target test first failed because the built index still declared `Alidora — Cordia`. The dashboard source index was changed to `Workspace — Cordia`, normalized to LF, and rebuilt. The production-target suite then passed 2/2.

## Navigation inventory

| Producer or entry | Result | Default |
| --- | --- | --- |
| Saved workspace Run control in `web/interfaces.html` | `/dashboard/?workspace=<encoded-safe-id>` | Workspace |
| Builder save completion in `web/builder.html` | `/dashboard/?workspace=<encoded-safe-id>` | Workspace |
| Legacy `web/interface.html?id=<id>` | Valid id redirects to `/dashboard/?workspace=<encoded-safe-id>` | Workspace |
| Legacy missing, path-shaped, drive-shaped, credential-shaped, or overlong id | `/interfaces.html` | Fail closed |
| Alidora navigation helper | `/dashboard/?workspace=<same-id>&view=alidora` | Explicit advanced view |
| Dashboard internal view navigation | Retains the same workspace id; unknown view values normalize to Workspace | Workspace |
| Cordia root, Surveyor, profile, saved-list, and builder paths | No `view=alidora` producer | Cordia primary |

The shared grammar accepts canonical digit-leading 32-character lowercase UUID hex values and existing 1–80 character alphanumeric safe ids with `.`, `_`, or `-`. It rejects slashes, backslashes, colons/drive prefixes, credential prefixes, and overlong values. Legacy redirect logic reads only `id`; unrelated query keys are not reflected into markup or navigation.

## Authentication and ownership review

- The dashboard continues to load canonical state through authenticated `/surveyor/*` calls using the existing credential/session behavior.
- Existing explicit signed-out and offline UI remains in `WorkspaceView`; dashboard tests cover signed-out error classification and bounded signed-out copy.
- No query token, second auth gate, second persisted workspace state, connector registry, approval path, execution path, outcome loop, or secret path was added.
- Cordia remains the only state and execution owner. Alidora remains an explicit read-only projection from `/surveyor/alidora/map`.
- The existing GitHub read-only route and auth verification behavior were not modified.

## Reproducible build

Clean install command and result:

```powershell
Set-Location dashboard-app
npm.cmd ci
```

Result: 137 packages installed from the committed lockfile, 138 packages audited, 0 vulnerabilities. The first sandboxed attempt could not read the user npm cache; the approved rerun of the same command completed successfully.

Build command and result:

```powershell
npm.cmd run build
```

Result: Vite 7.3.6 transformed 198 modules and completed successfully in 2.48 seconds. Final output:

- `web/dashboard/index.html` — 0.73 kB, gzip 0.42 kB
- `web/dashboard/assets/index-CAVEeD60.css` — 24.67 kB, gzip 4.87 kB
- `web/dashboard/assets/index-vABXlzzo.js` — 401.19 kB, gzip 128.41 kB

The build removed obsolete generated hashes only within `web/dashboard/assets`: `index-B1mzUD5h.js` and `index-BYbymIe1.css`.

## Exact committed production assets

SHA-256:

```text
cf73d82dbd5ecba437866c007ff01962f17fa3fda00d26128dccd06fdc625601  web/dashboard/index.html
df1cb77ac8658b97fc9bc5bf54e2ace0e649b0a3f957076a0d59504c1e92d887  web/dashboard/assets/index-CAVEeD60.css
fc9b0712bc4885ce04bc21bd0168d33e60cca2a4d00b7a3ed7bb8251c2dd74b9  web/dashboard/assets/index-vABXlzzo.js
```

The production-target test parses `web/dashboard/index.html`, resolves every `/dashboard/` reference below `web/dashboard`, verifies each file exists in the Git index, and checks the JavaScript bundle for Workspace primary, Alidora advanced, explicit missing-workspace UI, and the fixed `/surveyor/workspace`, `/surveyor/alidora/map`, `/surveyor/run`, and `/surveyor/skill/execute` contracts.

## Full verification

- Dashboard: `npm.cmd test` — 36 passed, 0 failed.
- Desktop: `npm.cmd test` — 44 passed, 0 failed.
- Backend: Python 3.12 `-m unittest discover -s tests -v` — 143 passed, 0 failed.
- Build: `npm.cmd run build` — success, 198 modules transformed.
- Syntax: `node --check` passed for changed standalone JavaScript (`workspace-navigation.js`, `api.js`, `workspace-view.js`).
- Diff hygiene: both `git diff --check` and `git diff --cached --check` passed.
- Backend route scan: no `/dashboard/` backend/store/API surface.
- Unsafe generic-surface scan: no dashboard command/API/execute/skill/outcome/store route and no new child-process, spawn, shell, or exec surface in the scoped sources.
- Legacy producer scan: no tracked internal `interface.html?id=` producer outside compatibility tests/docs.
- Normal-flow scan: no `view=alidora` in root, Surveyor, profile, builder, or saved-list pages.

The backend suite emits expected environment notices that optional NumPy embedding scoring is unavailable and the test database hostname is unreachable; those paths remain deliberately non-blocking and all 143 tests pass.

## Self-review

- Confirmed every normal workspace producer uses the primary dashboard route.
- Confirmed Alidora uses the identical canonical id with only the explicit view parameter added.
- Confirmed the legacy page cannot reflect arbitrary query data and fails closed on all required hostile shapes.
- Confirmed invalid server-returned ids do not become navigation targets.
- Confirmed production title and bundled route/API contracts are Workspace-primary.
- Confirmed only reviewed branch sources produced the committed hashes.
- Confirmed obsolete generated files are limited to the Vite output directory.
- Confirmed no backend, auth, persistence, permission, connector-truth, execution, outcome, or secret ownership expansion.
- Confirmed the staged file list contains only Task 4 source, tests, compatibility route, generated bundle, and this report.

## Commit

This report is included in the Task 4 commit. Its exact immutable hash is reported in the task handoff because a Git commit cannot contain its own stable hash.

## Concerns

No Task 4 blocker remains. Public browser smoke testing, service-health verification, exact deployed-hash verification, and production rollout remain Task 5 work and are not claimed here.
