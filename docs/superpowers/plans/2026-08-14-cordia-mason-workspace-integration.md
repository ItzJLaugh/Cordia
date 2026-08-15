# Cordia + Mason Workspace Integration Plan

> **Execution:** Use subagent-driven development task-by-task with independent review after every task and a whole-branch review before release.

**Goal:** Replace the narrow legacy workspace presentation with Cordia's unified chat-first artifact workspace while adapting Mason's proven fast dashboard interaction and graph rendering into Alidora.

**Architecture:** Cordia remains the only owner of workspace state, artifacts, connectors, skills, permissions, approvals, secrets, outcomes, and execution. The existing authenticated `/surveyor/*` APIs remain authoritative. The React dashboard becomes one Cordia-owned shell with two views: the primary Workspace view and the advanced Alidora view. Mason's dashboard UI, graph geometry, race-safe selection, and chat interaction may be adapted; Mason's parallel `/dashboard/*` state, interface store, skill registry, execution path, and outcome loop are rejected.

**Source references:** `origin/feat/dashboard-chat` is the complete Mason dashboard stack. `docs/CORDIA_BUILD_CONTEXT.md`, `docs/TODO_CORDIA_VERTICAL_SLICE.md`, and `docs/ALIDORA_INTEGRATION_CHARTER.md` are binding.

## Global constraints

- Cordia is primary and chat-first. Alidora is a named advanced view, never the initial experience for a normal workspace entry.
- A saved workspace is loaded only from authenticated `GET /surveyor/workspace?id=...`; no frontend-owned or dashboard-owned workspace state is persisted.
- Workspace windows are Cordia agent-built artifacts. DashView is the default. LiveView is shown only when both the artifact contract says it is supported and the user has explicitly enabled it. This slice must not imply that LiveView is available.
- All connector, capability, skill, permission, approval, and activity truth comes from existing typed `/surveyor/*` APIs. Catalog entries marked planned must never appear connected or runnable.
- Skill buttons inject a bounded, human-readable skill request into the Cordia assistant and submit it immediately. Execution still goes through the existing typed skill endpoint and permission gateway; the UI adds no generic command path.
- Alidora reads the safe canonical projection from `GET /surveyor/alidora/map?id=...`; it does not author or execute in this slice.
- Preserve auth behavior and the existing GitHub read-only connector path.
- No raw secrets, tokens, local paths, arbitrary connector payloads, or cross-user workspace identifiers may enter renderer output.
- Production claims require source tests, a reproducible Vite build, public browser smoke tests, service health, and verification of the deployed asset hashes.

## Adopt / adapt / compose / reject ruling

| Mason component | Decision | Integration rule |
| --- | --- | --- |
| Split chat + canvas shell | Adapt | Becomes Cordia Workspace layout with Cordia visual system and artifact grid. |
| `ChatPanel` immediate interaction | Adapt | Uses existing Cordia run/skill APIs and visible permission states. |
| React Flow graph, geometry, approval edges, race-safe selection | Adopt/adapt | Lives only in Alidora and consumes the safe canonical map. |
| Loading, signed-out, offline, and limited states | Adopt | Retain explicit accessible states. |
| `/dashboard/*` backend and interface store | Reject | Duplicates canonical Surveyor/workspace ownership. |
| Dashboard skill registry/executor | Reject | Duplicates Cordia capability gateway and permission policy. |
| Dashboard outcome loop | Reject | Duplicates Cordia's bounded outcome/intent-miss pipeline. |

---

### Task 1: Define and test the canonical frontend workspace adapter

**Files:** create `dashboard-app/src/workspace.js`; create `dashboard-app/test/workspace.test.js`; update `dashboard-app/package.json` only if test discovery requires it.

- [ ] Write failing tests that transform a representative canonical `/surveyor/workspace` response into bounded artifact cards, workflow rows, and view-mode metadata.
- [ ] Require stable card ids/order, explicit `dash` view mode, truthful live/planned connector status, and omission of secret/path-shaped fields.
- [ ] Add tests for malformed input and for LiveView remaining unavailable unless both support and user-enable flags are true.
- [ ] Implement the smallest pure adapter. It performs no fetch, persistence, permission decision, or execution.
- [ ] Run `npm.cmd test` in `dashboard-app` and commit.

### Task 2: Build the unified Cordia Workspace shell

**Files:** create `dashboard-app/src/WorkspaceView.jsx`, `ArtifactCard.jsx`, and related focused tests; modify `dashboard-app/src/App.jsx`, `api.js`, `app.css`.

- [ ] Start with failing behavioral tests for route selection: normal workspace entry renders Cordia Workspace; `view=alidora` renders Alidora; missing/signed-out/offline states are explicit.
- [ ] Implement a left Cordia assistant and right artifact canvas patterned after the approved UI reference, without copying third-party product chrome.
- [ ] Load canonical workspace state from `/surveyor/workspace?id=...`; retain the selected workspace id in the URL.
- [ ] Render workflow, agent, connector, derived-note, mission/context, skill, capability, approval, and activity artifacts from canonical/bounded endpoints.
- [ ] Provide visible Workspace and Alidora navigation. Alidora stays read-only and uses `/surveyor/alidora/map`.
- [ ] Preserve keyboard navigation, accessible names, status/live regions, and narrow-screen behavior.
- [ ] Run focused tests plus `npm.cmd test`; commit.

### Task 3: Wire immediate skill-to-assistant interaction through existing gates

**Files:** modify `WorkspaceView.jsx`, `api.js`; create/update focused interaction tests.

- [ ] Write failing tests proving a runnable skill click inserts its bounded request into assistant history and submits immediately without a second send click.
- [ ] Prove unavailable/planned skills cannot invoke execution and instead explain the missing connector/permission prerequisite.
- [ ] Call only the fixed `/surveyor/skill/execute` endpoint for skill execution and `/surveyor/run` for ordinary workspace requests.
- [ ] Refresh affected canonical artifacts/activity after successful execution without creating client-owned truth.
- [ ] Surface ASK/DENY and protected-continuation limitations accurately.
- [ ] Run focused tests plus the complete dashboard suite; commit.

### Task 4: Make the unified workspace the discoverable production route

**Files:** modify `web/interface.html`, `web/interfaces.html`, `web/builder.html`, `web/assets/cordia-shell.js`, dashboard production-target tests, and build configuration as needed.

- [ ] Write failing navigation tests proving saved/new workspaces open the primary Workspace view and the Alidora control opens the advanced view for the same workspace id.
- [ ] Preserve old `interface.html?id=...` deep links with a safe redirect or compatibility shell to `/dashboard/?workspace=...`.
- [ ] Ensure normal sign-in/Surveyor/builder flows never land in Alidora by default.
- [ ] Build the dashboard from a clean dependency install and commit `web/dashboard/index.html` with every referenced hashed asset.
- [ ] Run navigation, auth, dashboard target, complete backend, desktop, dashboard, syntax, and diff checks; commit.

### Task 5: Whole-branch validation and live rollout

- [ ] Independently review the complete branch against the charter, this plan, permission boundaries, privacy, accessibility, and the target workspace experience.
- [ ] Resolve all Critical/Important findings and re-review the fix diff.
- [ ] Publish a focused PR from the integration branch and merge only after checks pass.
- [ ] Through Hostinger hPanel's VPS Web Console: inspect current production drift, create a rollback point, update without discarding server-only changes, rebuild/restart if required, and verify service health.
- [ ] Browser-smoke the public auth, Surveyor, builder, primary Workspace, Alidora, GitHub read-only window, skill gate, reload persistence, and old deep-link journey.
- [ ] Verify the public dashboard references the exact committed asset hashes and record remaining planned—not-live—capabilities truthfully.

