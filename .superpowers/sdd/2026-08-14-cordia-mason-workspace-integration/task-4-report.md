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

## Fix round 1: identifier boundary and committed provenance

### Findings addressed

1. The dashboard route, run API, and skill-execution API now share one identifier contract with the legacy navigation helper. All reject credential-shaped ids, including `sk-...`, `ghp_...`, `github_pat_...`, `AKIA...`, and `token.secret-value`, before constructing a query string or issuing a fetch.
2. The production-target test now validates Git index blobs rather than trusting worktree filenames. A deterministic build-provenance manifest binds the reviewed dashboard inputs to the exact emitted HTML, CSS, and JavaScript bytes.

### TDD evidence

The focused dashboard RED run executed 18 tests: 14 passed and 4 failed. The failures proved that run execution accepted `sk-...`, skill execution accepted `ghp_...`, the dashboard/legacy contracts disagreed for credential-shaped values, and dashboard route construction produced a URL for `sk-...`. After the shared validator and regressions were added, the same focused suite passed 18/18.

The production-target RED run executed 3 tests: 2 passed and the provenance test failed because `web/dashboard/build-provenance.json` did not exist. After the Vite provenance plugin, manifest, and committed-blob assertions were added, the focused suite passed 3/3.

### Identifier contract

`dashboard-app/src/identifier.js` is the single dashboard boundary used by route construction, workspace loading, run submission, and skill execution. The cross-contract regression loads the legacy navigation helper and verifies that both contracts agree over accepted canonical ids and every rejected credential family. Invalid values produce no workspace href, no query string, and no fetch.

### Reproducible reviewed-source provenance

The Vite build hashes a bounded, sorted input set: `package-lock.json`, `package.json`, `vite.config.js`, and every file under `src/`. Text line endings are normalized to LF before hashing so the same reviewed source produces the same manifest on supported development hosts. The manifest contains no timestamp, absolute path, environment value, or secret.

The clean build produced this source-input SHA-256:

```text
4dd46ad02383032584d8858429b19d68397e1880b484a77d46ddccf1f3adc860
```

Exact emitted-file SHA-256 values:

```text
8b58ead2b806d2164537a8c0f6be7effc336dad564ac6dcff3dcded287a8427a  web/dashboard/index.html
df1cb77ac8658b97fc9bc5bf54e2ace0e649b0a3f957076a0d59504c1e92d887  web/dashboard/assets/index-CAVEeD60.css
b010d57c53f925b0aa824ee8e70497855523a0b36d4ac1ecb3035e568013e10e  web/dashboard/assets/index-DpLf8F_q.js
5abc35fc9e04b2a9c71915676cbf24eb89d99bd2650d8bb1a103c8ff0c2426a9  web/dashboard/build-provenance.json
```

The production-target test independently recomputes the source hash from Git index blobs, resolves the output list from the committed index HTML, verifies every declared output hash against both its index blob and worktree bytes, and rejects provenance containing absolute paths, timestamps, or secret-bearing fields. With a clean index after commit, these index blobs are the exact HEAD blobs.

### Clean install, build, and verification

- `npm.cmd ci` — 137 packages installed, 138 audited, 0 vulnerabilities.
- `npm.cmd run build` — Vite 7.3.6 transformed 199 modules successfully.
- A second clean build reproduced the identical output paths and SHA-256 values (`REPRODUCIBLE_BUILD=clean`).
- Dashboard full suite — 37 passed, 0 failed.
- Desktop full suite — 45 passed, 0 failed.
- Backend Python 3.12 suite — 143 passed, 0 failed; only the previously documented optional NumPy and unreachable test-database notices were emitted.
- Standalone JavaScript syntax checks — clean for `identifier.js`, `api.js`, `workspace-view.js`, and `vite.config.js`.
- Worktree and staged diff checks — clean.
- Backend dashboard-route scan, unsafe generic-surface scan, and built credential-literal scan — clean.

### Fix-round commit and concerns

The exact fix-round commit hash is reported in the handoff because a commit cannot contain its own stable hash. No fix-round blocker remains. Deployment and public service verification remain Task 5 work.

## Fix round 2: HEAD-bound release derivation

### Finding addressed

The production-target checks now use `git show HEAD:<path>` for every dashboard source, config, lockfile, manifest, index, CSS, and JavaScript blob. Each HEAD blob must match the Git index exactly, so staged-but-uncommitted content fails the release test. Generated release files must also match worktree bytes exactly; source/config/lock worktree comparisons apply the manifest's declared LF normalization so platform checkout line endings do not create a false release difference.

An explicit committed release command, `npm.cmd run verify:dashboard-release` from `desktop/`, constructs a temporary isolated tree from only the exact HEAD dashboard input blobs. It runs fixed `npm ci` and `npm run build` commands with an isolated npm cache and secret-shaped/Vite/Cordia environment variables removed, then byte-compares the rebuilt index, CSS, JavaScript, and provenance manifest with their HEAD blobs. The verifier validates the temporary target before recursively removing it in a `finally` block.

### TDD and staged-content evidence

The first HEAD-bound production-target RED run executed 4 tests: 2 passed and 2 failed. One failure exposed Windows CRLF checkout bytes in `package-lock.json`; the comparison was corrected to use the provenance contract's LF normalization for text worktree inputs while retaining exact HEAD-to-index equality. The other failure showed the new verifier did not exist in HEAD. Before the implementation commit, the corrected focused suite remained 3/4 with the staged verifier rejected because it was absent from HEAD. This is the intended fail-closed result for staged-but-uncommitted release content.

Implementation commit:

```text
5f8cbdf  test(dashboard): verify release from HEAD blobs
```

### Post-commit verification

- Desktop full suite — 46 passed, 0 failed, including all 4 HEAD/index/worktree production-target tests.
- Focused dashboard route/API/credential contract — 18 passed, 0 failed.
- Explicit clean HEAD rebuild — 137 packages installed from the HEAD lockfile; Vite 7.3.6 transformed 199 modules; every rebuilt release file matched HEAD byte-for-byte.
- Source-input SHA-256 — `4dd46ad02383032584d8858429b19d68397e1880b484a77d46ddccf1f3adc860`.
- CSS SHA-256 — `df1cb77ac8658b97fc9bc5bf54e2ace0e649b0a3f957076a0d59504c1e92d887`.
- JavaScript SHA-256 — `b010d57c53f925b0aa824ee8e70497855523a0b36d4ac1ecb3035e568013e10e`.
- Provenance SHA-256 — `5abc35fc9e04b2a9c71915676cbf24eb89d99bd2650d8bb1a103c8ff0c2426a9`.
- Index SHA-256 — `8b58ead2b806d2164537a8c0f6be7effc336dad564ac6dcff3dcded287a8427a`.

Dashboard implementation sources and backend behavior did not change in this round, so the focused dashboard credential suite and full desktop suite were the relevant regression scope. No fix-round blocker remains; deployment and public service verification remain Task 5 work.
