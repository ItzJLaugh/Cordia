# Cordia Vertical Slice TODO

Last updated: 2026-08-18

This checklist is the implementation companion to:

- `docs/CORDIA_BUILD_CONTEXT.md`
- `docs/WORKSPACE_FDE_PIVOT_CONTEXT.md`
- `docs/CODING_AGENT_BOOTSTRAP.md`

The goal is not to implement every connector or every long-term feature at once. The goal is to prove the smallest real end-to-end personal-FDE loop.

## Status and evidence legend

- `[x]` means the exact product behavior or contract has both implementation and a direct automated test for that same claim. Adjacent foundations and separately tested components do not establish integration or end-to-end completion.
- `[ ]` means the behavior is missing, partial, documentation-only, supported only by an adjacent component, or still needs direct automated or end-to-end proof.
- Current boundaries remain deliberate: GitHub is the only live cloud connector; an `ASK` checkpoint does not yet resume a protected external write; desktop installer/cloud-sync E2E is incomplete; and Alidora is an authenticated read-only foundation.

Compact evidence index:

- Surveyor artifacts and bounded operator-profile contract: `backend/surveyor/artifacts.py`, `backend/surveyor/operator_profile.py`, `backend/surveyor/pipeline.py`, `backend/tests/test_artifacts.py`, `backend/tests/test_operator_profile.py`, and `web/test/operator_profile.test.js`.
- Canonical workspace and DashView: `backend/surveyor/workspace_state.py`, `dashboard-app/src/workspace-view.js`, `backend/tests/test_workspace_state.py`, `dashboard-app/test/workspace*.test.js`.
- Alidora read-only projection: `backend/surveyor/alidora.py`, `dashboard-app/src/graph.js`, `backend/tests/test_alidora.py`, `dashboard-app/src/graph.test.js`.
- Connector, skill, and permission boundaries: `backend/surveyor/{capability_gateway,skills,permissions,github_connector}.py` and their matching `backend/tests/test_*.py` files.
- Secret handling: `backend/surveyor/vault.py`, the GitHub execution boundary in `backend/training_backend.py`, and `backend/tests/test_vault.py`.
- Desktop foundations: `desktop/{main,local_repository,git_adapter,git_skills,local_approvals}.js` and `desktop/test/*.test.js`. These components do not yet prove install, account/workspace sync, or canonical product integration.

---

# Phase 0 — Inspect Before Changing

- [ ] Inspect the current repository structure.
- [ ] Locate existing Surveyor implementation.
- [ ] Locate existing profile/assessment implementation.
- [ ] Locate workspace/workspace-builder implementation.
- [ ] Locate existing connector catalog/manifests.
- [ ] Locate existing tool/MCP/runtime code.
- [ ] Locate existing permission/scope logic.
- [ ] Locate existing frontend design system.
- [ ] Locate existing desktop/local/runtime code, if any.
- [ ] Produce a current-state architecture map before broad refactoring.
- [ ] Identify which existing contracts can be reused.
- [ ] Identify any conflicts with the current canonical context docs.

---

# Phase 1 — Surveyor → Source Artifacts

- [ ] Ensure Surveyor remains conversational rather than form-first.
- [ ] Persist Surveyor conversation/evidence.
- [x] Generate/update `operator.md` from Surveyor evidence.
- [x] Generate/update `connectors.md` from Surveyor evidence and user confirmation.
- [x] Create `intent-misses.md` as structured appendable memory.
- [ ] Store evidence and confidence for inferred profile signals.
- [x] Keep raw transcript/history separate from compiled runtime context where practical.

Acceptance criteria:

- [ ] A new user can complete a short Surveyor conversation.
- [x] Cordia produces an inspectable `operator.md`.
- [x] Cordia produces an inspectable `connectors.md`.
- [x] No numeric overall assessment score is required.

---

# Phase 2 — Compile FDE Runtime Artifacts

- [ ] Create compiler/process that combines `operator.md` + `connectors.md` + `intent-misses.md` + current workspace goals.
- [x] Generate/update `fde-tasks.md` as the living mission brief.
- [x] Generate/update `permissions.md`.
- [x] Generate/update `workspace-plan.md`.
- [x] Keep source artifacts separate from compiled artifacts.
- [x] Ensure `fde-tasks.md` stays concise and operational, not a transcript dump.

Acceptance criteria:

- [x] `fde-tasks.md` states what Cordia should actually do for the user.
- [x] `permissions.md` expresses ALLOW / ASK / DENY behavior.
- [x] `workspace-plan.md` describes the visual workspace to render.

---

# Phase 3 — Assessment View

- [x] Build Surveyor assessment page from artifact/profile data.
- [x] Remove overall score/percentile/pass-fail framing.
- [x] Show “What Cordia understands.”
- [x] Show profile signals using descriptive levels such as High / Medium / Emerging.
- [x] Show evidence snippets.
- [x] Show inferred/confirmed applications/connectors.
- [x] Show what Cordia is still learning.
- [x] Allow user to reopen Surveyor and refine the profile.
- [x] Provide a clear next action to build/open the workspace.

Acceptance criteria:

- [x] The assessment feels like an inspectable operator profile, not a test result.

Evidence boundary: `/surveyor/operator-profile` is an authenticated, owner-scoped,
read-only projection of existing Surveyor profile, connector, and workspace state.
The browser receives bounded descriptive evidence and fixed navigation only; it
does not receive scoring criteria, numeric confidence/completeness, raw artifacts,
workspace definitions, secrets, or local paths. Public signed-in deployment
verification remains a release check rather than source-level evidence.

---

# Phase 4 — Canonical Workspace State

- [x] Define or reconcile a single canonical `Workspace` contract.
- [x] Include windows.
- [x] Include connectors.
- [x] Include skills.
- [x] Include agents if needed.
- [x] Include permissions.
- [x] Include context sources.
- [ ] Include automations.
- [x] Include mutations.
- [x] Include provenance.
- [x] Include connector/runtime status.
- [ ] Include future desktop/local capability status.
- [ ] Ensure both user edits and Cordia-agent edits mutate the same state.

Acceptance criteria:

- [ ] Workspace UI can be reconstructed entirely from canonical workspace state.
- [ ] No separate hidden “AI layout” state is required.

---

# Phase 5 — Workspace Frontend

- [ ] Match Cordia visual theme: warm ivory/soft white, dark olive, restrained borders, floating panels, clean modern research-lab feel.
- [ ] Use actual Cordia logo/wordmark assets available in the repository.
- [ ] Create full-height Cordia Agent panel on the left.
- [ ] Create visual workspace surface on the right.
- [x] Create bottom inspection dock.
- [x] Dock tabs: Connected / Skills / Access / Context / Automations / Activity.
- [ ] Avoid node-graph edges between application windows.
- [x] Render windows from canonical workspace state.
- [ ] Support window move/resize if already aligned with existing contracts.
- [ ] Make builder and runtime the same surface.

Acceptance criteria:

- [ ] User can see Cordia Agent and workspace simultaneously.
- [ ] Workspace changes appear immediately after state mutations.

Evidence boundary: the primary React Workspace has a six-tab, read-only inspection
dock derived from the existing renderer-safe workspace projection. Existing artifact
cards remain the only skill-action surface, and Alidora does not render the dock.
Automations reports a configured-empty state only for canonical `automations: []`;
unknown and non-empty shapes remain unavailable until a typed automation contract
exists. Public deployment and interactive browser verification remain release checks.

---

# Phase 5A — Alidora Foundation: Agentic System Builder

Alidora is the advanced Cordia module for building and operating company agentic systems. It is not a parallel workspace/runtime.

**Current review status:** The packaged, authenticated, read-only System Map is implemented and awaiting independent re-review. It visibly projects safe agent/skill topology and catalog-backed connector consent/implementation/lifecycle/runtime state from the canonical workspace. Permissions, provenance, artifact purpose/source/view-mode/action inspection, authoring, execution, connector setup, LiveView, approval decisions, runs, and traces remain deferred.

- [x] Add an Alidora entry point/tab to the Cordia product information architecture.
- [x] Reuse canonical workspace state; do not create graph-only state ownership.
- [x] Project safe canonical agent/skill topology and truthful connector state into a read-only Workspace Map/System View.
- [ ] Display permissions and provenance in the Workspace Map/System View.
- [ ] Inspect artifact purpose, sources, view mode, and action requirements.
- [x] Keep Cordia's conversational cockpit as the default surface.
- [ ] Route from Alidora actions through the same typed capability gateway and ALLOW / ASK / DENY enforcement.
- [ ] Surface run status, approval checkpoints, provenance, and safe traces without exposing secrets or local paths.
- [ ] Reuse/adapt verified graph and workflow components only after contract review.
- [ ] Do not add a second skill registry, connector catalog, outcome loop, or execution path.

Acceptance criteria:

- [x] A workspace has one visible, read-only topology projection derived from canonical state.
- [ ] An Alidora action cannot bypass Cordia permissions, approvals, audit, or capability confirmation.
- [ ] A user can return from Alidora to the Cordia workspace without losing shared state.

---

# Phase 6 — Connector-Native Window Registry

**Current evidence boundary:** The primary React Workspace conditionally reads the existing authenticated `GET /surveyor/github/repositories` endpoint only for canonical confirmed/live GitHub state, then renders a bounded native DashView repository artifact. `dashboard-app/test/workspace-view.test.js` proves fetch gating, first-read behavior, 30-item bounding, safe deterministic projection, and truthful unavailable/needs-attention states; `dashboard-app/test/artifact-card.test.js` proves the projected summary detail renders. The fixed `web/github.html` route remains setup/detail/recovery. Public deployment verification is still pending.

- [ ] Create or reconcile a window renderer registry keyed by connector/view/skill.
- [ ] Implement one fake/mock connector renderer first.
- [x] Implement one real cloud connector renderer.
- [x] Prefer Cordia-native data surfaces over iframes.
- [ ] Allow derived windows backed by skills rather than a single connector.

Suggested first real cloud connector:

- [x] Google Drive, Notion, or GitHub — choose based on current repo support and simplest real auth/data path.

Acceptance criteria:

- [x] A live connector can render real data in a Cordia-native window.

---

# Phase 7 — Capability Hierarchy

- [x] Reconcile connector model.
- [x] Reconcile primitive tool model.
- [x] Add deterministic script layer where useful.
- [x] Add skill manifest/registry for human-level capabilities.
- [x] Ensure skills declare required connectors/tools/permissions.
- [x] Avoid defining UI clicks as skills.
- [ ] Allow a derived window to be recommended by a skill.

Acceptance criteria:

- [ ] Cordia Agent can choose a meaningful skill rather than a sequence of arbitrary UI actions.

---

# Phase 8 — Cordia MCP Gateway

- [ ] Make the Cordia MCP server/gateway the unified capability layer.
- [ ] Ensure the dashboard is not conflated with the MCP server.
- [ ] Expose typed tools to the Cordia Agent.
- [ ] Route typed tools to connector-specific implementations.
- [ ] Hide whether the backend uses REST, curl, browser automation, CLI, local script, or another MCP server.
- [ ] Add audit/provenance around tool calls.
- [x] Enforce permission checks before execution.

Acceptance criteria:

- [ ] Cordia Agent can call one typed capability through the MCP gateway and receive a structured result.

---

# Phase 9 — Permissions Runtime

**Current evidence boundary:** ALLOW / ASK / DENY decisions, execution gates, and checkpoint primitives have component tests. The authenticated Review GitHub repositories skill now proves one real ALLOW read through the existing skill and capability gates, returns only a bounded count receipt to chat, and triggers one canonical DashView refresh. No user-accessible ASK action with protected external-write continuation or resume has been proven.

- [x] Implement ALLOW / ASK / DENY.
- [x] Bind tool/skill execution to required permissions.
- [ ] Add approval pause for ASK.
- [x] Add hard block for DENY.
- [ ] Expose permission state in the Access UI.
- [ ] Ensure permission behavior is for the Cordia agent, not human RBAC roles.

Acceptance criteria:

- [x] One real action is allowed automatically.
- [ ] One real action pauses for approval.
- [ ] One real action is denied.

---

# Phase 10 — Intent-Miss Loop

**Current evidence boundary:** After a real Cordia response, the primary React Workspace exposes a bounded correction form that posts one allow-listed category, correction, and future effect to the existing authenticated intent-miss endpoint. A successful write refreshes that same workspace's canonical artifact feeds; cancellation discards the browser draft, Alidora remains read-only, and failures retain the draft with bounded recovery copy. Dashboard API/component tests cover that UI boundary. A route-level backend integration test now proves one authenticated workspace run, correction, recompilation, and subsequent run: the saved effect enters the next runtime prompt and the deterministic Limited-mode response acknowledges that saved guidance without echoing the raw correction. This proves propagation and acknowledgement, not substantive model compliance with the requested effect.

- [x] Add UI path for user to say an output missed intent.
- [x] Capture structured miss category.
- [x] Capture user correction.
- [x] Append/update `intent-misses.md`.
- [x] Recompile relevant `fde-tasks.md` guidance.
- [x] Make Limited mode visibly acknowledge compiled saved guidance without echoing raw correction text.
- [ ] Keep MVP weighting simple and inspectable.

Possible miss categories:

- [x] Missing context
- [x] Wrong audience
- [x] Too generic
- [x] Needs evidence
- [x] Wrong format
- [x] Wrong constraint
- [x] Unsafe to automate
- [x] Needs human checkpoint

Acceptance criteria:

- [ ] A correction made once can change subsequent Cordia behavior for the same workspace.

---

# Phase 11 — Guided Connector Setup

- [x] Add connector setup strategy to connector manifest/schema.
- [ ] Support at least one setup mode such as OAuth or guided browser API-key setup.
- [ ] Add Lightpanda/browser setup adapter if appropriate for the chosen connector.
- [ ] Allow Cordia to prefill known email only if allowed.
- [ ] Require user to enter password/2FA directly.
- [ ] Ensure agent cannot read/store password values.
- [ ] Pause before sensitive token generation if the flow requires human confirmation.
- [ ] Capture generated token directly into encrypted secret storage.
- [x] Return `secret_ref`/status to the agent instead of raw secret for the current GitHub token route.
- [ ] Validate connector using direct API/curl after setup.
- [ ] Prefer direct runtime after browser-assisted setup.
- [ ] Destroy/expire setup browser session after completion.

Acceptance criteria:

- [ ] A nontechnical user can connect one API-key-based service without manually copying the API key into Cordia.

---

# Phase 12 — Secret Handling

**Current evidence boundary:** The vault and opaque reference contracts have direct tests. A route-level sentinel test now proves the existing authenticated GitHub setup-to-ALLOW-skill path: validation receives the raw token only at the adapter boundary, persistence receives only ciphertext plus a bounded opaque reference, unconfirmed state stops before lookup, execution resolves only inside the allowed capability closure, and responses/audits exclude token, ciphertext, provider rows, and local paths. A malformed stored reference fails closed before decryption or adapter use. The test uses a deterministic adapter double, so a live external GitHub request, arbitrary token-bearing network restrictions, and broad claims about every future prompt remain open.

- [x] Add encrypted secret store/vault abstraction.
- [ ] Never inject raw secrets into normal LLM prompt context.
- [x] Use `secret_ref` handles.
- [x] Resolve secrets only at the current GitHub ALLOW execution boundary.
- [ ] Restrict arbitrary token-bearing network calls.
- [x] Log current GitHub secret usage without logging secret values.

Acceptance criteria:

- [ ] Agent runtime can successfully execute a connector tool without ever receiving the raw API key in its visible context.

---

# Phase 13 — Browser Setup vs Durable Runtime

- [ ] Document and enforce browser-first only where setup requires it.
- [ ] Use Lightpanda/browser for login/setup/navigation/fallback.
- [x] Use direct API/curl/MCP for repeatable runtime actions whenever possible.
- [ ] Avoid browser automation for durable operations when a stable API exists.

Acceptance criteria:

- [ ] Chosen connector is configured with browser assistance if necessary, then operated through direct typed tools afterward.

---

# Phase 14 — Save Cloud Workspace

- [ ] Persist the completed workspace against the user’s Cordia account.
- [ ] Persist workspace artifacts/configuration.
- [ ] Persist connector status and secret references.
- [ ] Persist permissions.
- [ ] Persist window layout.
- [ ] Persist mutation/provenance history as appropriate.

Acceptance criteria:

- [ ] User can log out/in and recover the same workspace.

---

# Phase 15 — Desktop Install Entry Point

Critical sequencing requirement: this happens **after** the web workspace is already built and saved.

- [ ] Add “Install Cordia Desktop” action to completed/saved workspace.
- [ ] Provide `install.ps1` for Windows desktop installation.
- [ ] Do not make `install.ps1` part of initial workspace generation.
- [ ] Ensure install flow installs the Cordia Desktop App rather than constructing a second unrelated workspace.

Acceptance criteria:

- [ ] User can build the workspace entirely in the web app before ever installing the desktop app.

---

# Phase 16 — Cordia Desktop App

**Current evidence boundary:** Tested Electron shell, repository inspection, Git command, and local approval components exist. A packaged install, same-account cloud-workspace load, canonical state sync, and user-accessible local capability path remain unproven and therefore stay open below.

- [ ] Install desktop shell/app.
- [ ] User signs in with same Cordia email/account.
- [ ] Desktop app downloads/pulls the same saved workspace.
- [ ] Same Cordia Agent remains embedded.
- [ ] Same windows/configuration appear.
- [ ] User can continue modifying the workspace.
- [ ] Cloud workspace state remains authoritative/synchronized unless a future local-first design explicitly changes this.

Acceptance criteria:

- [ ] The desktop experience looks and behaves like the workspace the user already built on the web.

---

# Phase 17 — Desktop Local Bridge

- [ ] Register desktop device.
- [ ] Start local bridge/runtime.
- [ ] Discover supported local capabilities.
- [ ] Report local capability availability to Cordia workspace.
- [ ] Add one local capability first.

Suggested first local capability:

- [ ] local project/repo read access OR Claude Code adapter, depending on current repo support.

Potential future local capabilities:

- [ ] Claude Code
- [ ] local repo
- [ ] local filesystem
- [ ] PowerShell
- [ ] Python scripts
- [ ] Docker
- [ ] VS Code project
- [ ] terminal
- [ ] local MCP servers

- [ ] Enforce ALLOW / ASK / DENY locally.

Acceptance criteria:

- [ ] Desktop app reports and executes one local capability through the same Cordia capability model.

---

# Phase 18 — First Real End-to-End Demo

The first meaningful demo should prove this path:

```text
Surveyor conversation
        ↓
operator.md + connectors.md
        ↓
fde-tasks.md + permissions.md + workspace-plan.md
        ↓
non-scored assessment
        ↓
workspace generated
        ↓
Cordia Agent changes workspace through chat
        ↓
one real connector is configured
        ↓
one skill executes through Cordia MCP gateway
        ↓
workspace visibly updates
        ↓
user records an intent miss
        ↓
fde-tasks.md is refined
        ↓
workspace is saved
        ↓
user installs Cordia Desktop with install.ps1
        ↓
same workspace loads locally
        ↓
one local capability becomes available
```

Do not expand to ten connectors until this loop works.

The first Alidora demo follows the real vertical slice rather than replacing it:

```text
saved Cordia workspace
        ↓
Alidora Workspace Map projects the same canonical state
        ↓
user inspects agents, skills, connectors, and approval checkpoints
        ↓
an approved system change routes through Cordia's existing capability and audit path
        ↓
both Cordia Workspace and Alidora reflect the same result
```

---

# Phase 19 — Validation Metrics

Track whether Cordia is actually removing integration hops.

Potential MVP metrics:

- [ ] Time from account creation to first useful workspace.
- [ ] Time from “connect X” request to live connector.
- [ ] Number of manual technical setup steps required from user.
- [ ] Number of times user must leave Cordia during setup.
- [ ] Time to first useful output.
- [ ] Number of workspace edits before user accepts layout.
- [ ] Number of intent corrections after first output.
- [ ] Percentage of connector setup completed by Cordia vs user.
- [ ] Number of ASK approvals vs DENY blocks vs ALLOW actions.
- [ ] User-rated “matches what I meant” outcome.

The product should eventually prove that it reduces technical integration burden, not merely look easier.

---

# Implementation Rule

If the current repository already contains a valid implementation for any item above, do not recreate it under a second architecture.

Map the existing implementation to the intended contract, preserve what is sound, and modify only what is necessary to complete the real vertical slice.
