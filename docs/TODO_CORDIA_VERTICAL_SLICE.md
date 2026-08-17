# Cordia Vertical Slice TODO

Last updated: 2026-08-16

This checklist is the implementation companion to:

- `docs/CORDIA_BUILD_CONTEXT.md`
- `docs/WORKSPACE_FDE_PIVOT_CONTEXT.md`
- `docs/CODING_AGENT_BOOTSTRAP.md`

The goal is not to implement every connector or every long-term feature at once. The goal is to prove the smallest real end-to-end personal-FDE loop.

## Status and evidence legend

- `[x]` means the behavior is present in the repository and has direct source-and-test evidence. It does **not** by itself mean the complete public-host user journey has been re-verified.
- `[ ]` means the behavior is missing, partial, documentation-only, or still needs direct automated or end-to-end proof.
- Current boundaries remain deliberate: GitHub is the only live cloud connector; an `ASK` checkpoint does not yet resume a protected external write; desktop installer/cloud-sync E2E is incomplete; and Alidora is an authenticated read-only foundation.

Compact evidence index:

- Surveyor artifacts and assessment contract: `backend/surveyor/artifacts.py`, `backend/surveyor/pipeline.py`, `backend/tests/test_artifacts.py`, `backend/tests/test_intent_misses.py`.
- Canonical workspace and DashView: `backend/surveyor/workspace_state.py`, `dashboard-app/src/workspace-view.js`, `backend/tests/test_workspace_state.py`, `dashboard-app/test/workspace*.test.js`.
- Alidora read-only projection: `backend/surveyor/alidora.py`, `dashboard-app/src/graph.js`, `backend/tests/test_alidora.py`, `dashboard-app/src/graph.test.js`.
- Connector, skill, and permission boundaries: `backend/surveyor/{capability_gateway,skills,permissions,github_connector}.py` and their matching `backend/tests/test_*.py` files.
- Secret handling: `backend/surveyor/vault.py`, the GitHub execution boundary in `backend/training_backend.py`, and `backend/tests/test_vault.py`.
- Desktop foundations: `desktop/{main,local_repository,git_adapter,git_skills,local_approvals}.js` and `desktop/test/*.test.js`.

---

# Phase 0 — Inspect Before Changing

- [x] Inspect the current repository structure.
- [x] Locate existing Surveyor implementation.
- [x] Locate existing profile/assessment implementation.
- [x] Locate workspace/workspace-builder implementation.
- [x] Locate existing connector catalog/manifests.
- [x] Locate existing tool/MCP/runtime code.
- [x] Locate existing permission/scope logic.
- [x] Locate existing frontend design system.
- [x] Locate existing desktop/local/runtime code, if any.
- [x] Produce a current-state architecture map before broad refactoring.
- [x] Identify which existing contracts can be reused.
- [x] Identify any conflicts with the current canonical context docs.

---

# Phase 1 — Surveyor → Source Artifacts

- [ ] Ensure Surveyor remains conversational rather than form-first.
- [ ] Persist Surveyor conversation/evidence.
- [x] Generate/update `operator.md` from Surveyor evidence.
- [x] Generate/update `connectors.md` from Surveyor evidence and user confirmation.
- [x] Create `intent-misses.md` as structured appendable memory.
- [x] Store evidence and confidence for inferred profile signals.
- [x] Keep raw transcript/history separate from compiled runtime context where practical.

Acceptance criteria:

- [ ] A new user can complete a short Surveyor conversation.
- [x] Cordia produces an inspectable `operator.md`.
- [x] Cordia produces an inspectable `connectors.md`.
- [x] No numeric overall assessment score is required.

---

# Phase 2 — Compile FDE Runtime Artifacts

- [x] Create compiler/process that combines `operator.md` + `connectors.md` + `intent-misses.md` + current workspace goals.
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

- [ ] Build Surveyor assessment page from artifact/profile data.
- [ ] Remove overall score/percentile/pass-fail framing.
- [x] Show “What Cordia understands.”
- [x] Show profile signals using descriptive levels such as High / Medium / Emerging.
- [x] Show evidence snippets.
- [x] Show inferred/confirmed applications/connectors.
- [ ] Show what Cordia is still learning.
- [ ] Allow user to reopen Surveyor and refine the profile.
- [ ] Provide a clear next action to build/open the workspace.

Acceptance criteria:

- [ ] The assessment feels like an inspectable operator profile, not a test result.

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
- [x] Include future desktop/local capability status.
- [x] Ensure both user edits and Cordia-agent edits mutate the same state.

Acceptance criteria:

- [x] Workspace UI can be reconstructed entirely from canonical workspace state.
- [ ] No separate hidden “AI layout” state is required.

---

# Phase 5 — Workspace Frontend

- [ ] Match Cordia visual theme: warm ivory/soft white, dark olive, restrained borders, floating panels, clean modern research-lab feel.
- [ ] Use actual Cordia logo/wordmark assets available in the repository.
- [ ] Create full-height Cordia Agent panel on the left.
- [x] Create visual workspace surface on the right.
- [ ] Create bottom inspection dock.
- [ ] Dock tabs: Connected / Skills / Access / Context / Automations / Activity.
- [x] Avoid node-graph edges between application windows.
- [x] Render windows from canonical workspace state.
- [ ] Support window move/resize if already aligned with existing contracts.
- [ ] Make builder and runtime the same surface.

Acceptance criteria:

- [x] User can see Cordia Agent and workspace simultaneously.
- [x] Workspace changes appear immediately after state mutations.

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
- [x] Reuse/adapt verified graph and workflow components only after contract review.
- [x] Do not add a second skill registry, connector catalog, outcome loop, or execution path.

Acceptance criteria:

- [x] A workspace has one visible, read-only topology projection derived from canonical state.
- [ ] An Alidora action cannot bypass Cordia permissions, approvals, audit, or capability confirmation.
- [x] A user can return from Alidora to the Cordia workspace without losing shared state.

---

# Phase 6 — Connector-Native Window Registry

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

- [x] Cordia Agent can choose a meaningful skill rather than a sequence of arbitrary UI actions.

---

# Phase 8 — Cordia MCP Gateway

- [ ] Make the Cordia MCP server/gateway the unified capability layer.
- [x] Ensure the dashboard is not conflated with the MCP server.
- [x] Expose typed tools to the Cordia Agent.
- [x] Route typed tools to connector-specific implementations.
- [ ] Hide whether the backend uses REST, curl, browser automation, CLI, local script, or another MCP server.
- [ ] Add audit/provenance around tool calls.
- [x] Enforce permission checks before execution.

Acceptance criteria:

- [ ] Cordia Agent can call one typed capability through the MCP gateway and receive a structured result.

---

# Phase 9 — Permissions Runtime

- [x] Implement ALLOW / ASK / DENY.
- [x] Bind tool/skill execution to required permissions.
- [x] Add approval pause for ASK.
- [x] Add hard block for DENY.
- [ ] Expose permission state in the Access UI.
- [x] Ensure permission behavior is for the Cordia agent, not human RBAC roles.

Acceptance criteria:

- [x] One real action is allowed automatically.
- [x] One real action pauses for approval.
- [ ] One real action is denied.

---

# Phase 10 — Intent-Miss Loop

- [ ] Add UI path for user to say an output missed intent.
- [x] Capture structured miss category.
- [x] Capture user correction.
- [x] Append/update `intent-misses.md`.
- [x] Recompile relevant `fde-tasks.md` guidance.
- [x] Keep MVP weighting simple and inspectable.

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
- [x] Support at least one setup mode such as OAuth or guided browser API-key setup.
- [ ] Add Lightpanda/browser setup adapter if appropriate for the chosen connector.
- [ ] Allow Cordia to prefill known email only if allowed.
- [ ] Require user to enter password/2FA directly.
- [ ] Ensure agent cannot read/store password values.
- [ ] Pause before sensitive token generation if the flow requires human confirmation.
- [ ] Capture generated token directly into encrypted secret storage.
- [x] Return `secret_ref`/status to the agent instead of raw secret.
- [x] Validate connector using direct API/curl after setup.
- [ ] Prefer direct runtime after browser-assisted setup.
- [ ] Destroy/expire setup browser session after completion.

Acceptance criteria:

- [ ] A nontechnical user can connect one API-key-based service without manually copying the API key into Cordia.

---

# Phase 12 — Secret Handling

- [x] Add encrypted secret store/vault abstraction.
- [x] Never inject raw secrets into normal LLM prompt context.
- [x] Use `secret_ref` handles.
- [x] Resolve secrets only at execution boundary.
- [x] Restrict arbitrary token-bearing network calls.
- [ ] Log secret usage without logging secret values.

Acceptance criteria:

- [x] Agent runtime can successfully execute a connector tool without ever receiving the raw API key in its visible context.

---

# Phase 13 — Browser Setup vs Durable Runtime

- [ ] Document and enforce browser-first only where setup requires it.
- [ ] Use Lightpanda/browser for login/setup/navigation/fallback.
- [x] Use direct API/curl/MCP for repeatable runtime actions whenever possible.
- [x] Avoid browser automation for durable operations when a stable API exists.

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

- [ ] Install desktop shell/app.
- [ ] User signs in with same Cordia email/account.
- [ ] Desktop app downloads/pulls the same saved workspace.
- [x] Same Cordia Agent remains embedded.
- [x] Same windows/configuration appear.
- [ ] User can continue modifying the workspace.
- [x] Cloud workspace state remains authoritative/synchronized unless a future local-first design explicitly changes this.

Acceptance criteria:

- [ ] The desktop experience looks and behaves like the workspace the user already built on the web.

---

# Phase 17 — Desktop Local Bridge

- [ ] Register desktop device.
- [x] Start local bridge/runtime.
- [x] Discover supported local capabilities.
- [ ] Report local capability availability to Cordia workspace.
- [x] Add one local capability first.

Suggested first local capability:

- [x] local project/repo read access OR Claude Code adapter, depending on current repo support.

Potential future local capabilities:

- [ ] Claude Code
- [x] local repo
- [ ] local filesystem
- [ ] PowerShell
- [ ] Python scripts
- [ ] Docker
- [ ] VS Code project
- [ ] terminal
- [ ] local MCP servers

- [x] Enforce ALLOW / ASK / DENY locally.

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
