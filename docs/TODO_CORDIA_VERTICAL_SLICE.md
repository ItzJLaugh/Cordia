# Cordia Vertical Slice TODO

Last updated: 2026-08-14

This checklist is the implementation companion to:

- `docs/CORDIA_BUILD_CONTEXT.md`
- `docs/WORKSPACE_FDE_PIVOT_CONTEXT.md`
- `docs/CODING_AGENT_BOOTSTRAP.md`

The goal is not to implement every connector or every long-term feature at once. The goal is to prove the smallest real end-to-end personal-FDE loop.

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
- [ ] Generate/update `operator.md` from Surveyor evidence.
- [ ] Generate/update `connectors.md` from Surveyor evidence and user confirmation.
- [ ] Create `intent-misses.md` as structured appendable memory.
- [ ] Store evidence and confidence for inferred profile signals.
- [ ] Keep raw transcript/history separate from compiled runtime context where practical.

Acceptance criteria:

- [ ] A new user can complete a short Surveyor conversation.
- [ ] Cordia produces an inspectable `operator.md`.
- [ ] Cordia produces an inspectable `connectors.md`.
- [ ] No numeric overall assessment score is required.

---

# Phase 2 — Compile FDE Runtime Artifacts

- [ ] Create compiler/process that combines `operator.md` + `connectors.md` + `intent-misses.md` + current workspace goals.
- [ ] Generate/update `fde-tasks.md` as the living mission brief.
- [ ] Generate/update `permissions.md`.
- [ ] Generate/update `workspace-plan.md`.
- [ ] Keep source artifacts separate from compiled artifacts.
- [ ] Ensure `fde-tasks.md` stays concise and operational, not a transcript dump.

Acceptance criteria:

- [ ] `fde-tasks.md` states what Cordia should actually do for the user.
- [ ] `permissions.md` expresses ALLOW / ASK / DENY behavior.
- [ ] `workspace-plan.md` describes the visual workspace to render.

---

# Phase 3 — Assessment View

- [ ] Build Surveyor assessment page from artifact/profile data.
- [ ] Remove overall score/percentile/pass-fail framing.
- [ ] Show “What Cordia understands.”
- [ ] Show profile signals using descriptive levels such as High / Medium / Emerging.
- [ ] Show evidence snippets.
- [ ] Show inferred/confirmed applications/connectors.
- [ ] Show what Cordia is still learning.
- [ ] Allow user to reopen Surveyor and refine the profile.
- [ ] Provide a clear next action to build/open the workspace.

Acceptance criteria:

- [ ] The assessment feels like an inspectable operator profile, not a test result.

---

# Phase 4 — Canonical Workspace State

- [ ] Define or reconcile a single canonical `Workspace` contract.
- [ ] Include windows.
- [ ] Include connectors.
- [ ] Include skills.
- [ ] Include agents if needed.
- [ ] Include permissions.
- [ ] Include context sources.
- [ ] Include automations.
- [ ] Include mutations.
- [ ] Include provenance.
- [ ] Include connector/runtime status.
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
- [ ] Create bottom inspection dock.
- [ ] Dock tabs: Connected / Skills / Access / Context / Automations / Activity.
- [ ] Avoid node-graph edges between application windows.
- [ ] Render windows from canonical workspace state.
- [ ] Support window move/resize if already aligned with existing contracts.
- [ ] Make builder and runtime the same surface.

Acceptance criteria:

- [ ] User can see Cordia Agent and workspace simultaneously.
- [ ] Workspace changes appear immediately after state mutations.

---

# Phase 5A — Alidora Foundation: Agentic System Builder

Alidora is the advanced Cordia module for building and operating company agentic systems. It is not a parallel workspace/runtime.

- [ ] Add an Alidora entry point/tab to the Cordia product information architecture.
- [ ] Reuse canonical workspace state; do not create graph-only state ownership.
- [ ] Project canonical agents, skills, connectors, permissions, and provenance into a read-only Workspace Map/System View.
- [ ] Keep Cordia's conversational cockpit as the default surface.
- [ ] Route from Alidora actions through the same typed capability gateway and ALLOW / ASK / DENY enforcement.
- [ ] Surface run status, approval checkpoints, provenance, and safe traces without exposing secrets or local paths.
- [ ] Reuse/adapt verified graph and workflow components only after contract review.
- [ ] Do not add a second skill registry, connector catalog, outcome loop, or execution path.

Acceptance criteria:

- [ ] A workspace has one visible, inspectable graph projection derived from canonical state.
- [ ] An Alidora action cannot bypass Cordia permissions, approvals, audit, or capability confirmation.
- [ ] A user can return from Alidora to the Cordia workspace without losing shared state.

---

# Phase 6 — Connector-Native Window Registry

- [ ] Create or reconcile a window renderer registry keyed by connector/view/skill.
- [ ] Implement one fake/mock connector renderer first.
- [ ] Implement one real cloud connector renderer.
- [ ] Prefer Cordia-native data surfaces over iframes.
- [ ] Allow derived windows backed by skills rather than a single connector.

Suggested first real cloud connector:

- [ ] Google Drive, Notion, or GitHub — choose based on current repo support and simplest real auth/data path.

Acceptance criteria:

- [ ] A live connector can render real data in a Cordia-native window.

---

# Phase 7 — Capability Hierarchy

- [ ] Reconcile connector model.
- [ ] Reconcile primitive tool model.
- [ ] Add deterministic script layer where useful.
- [ ] Add skill manifest/registry for human-level capabilities.
- [ ] Ensure skills declare required connectors/tools/permissions.
- [ ] Avoid defining UI clicks as skills.
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
- [ ] Enforce permission checks before execution.

Acceptance criteria:

- [ ] Cordia Agent can call one typed capability through the MCP gateway and receive a structured result.

---

# Phase 9 — Permissions Runtime

- [ ] Implement ALLOW / ASK / DENY.
- [ ] Bind tool/skill execution to required permissions.
- [ ] Add approval pause for ASK.
- [ ] Add hard block for DENY.
- [ ] Expose permission state in the Access UI.
- [ ] Ensure permission behavior is for the Cordia agent, not human RBAC roles.

Acceptance criteria:

- [ ] One real action is allowed automatically.
- [ ] One real action pauses for approval.
- [ ] One real action is denied.

---

# Phase 10 — Intent-Miss Loop

- [ ] Add UI path for user to say an output missed intent.
- [ ] Capture structured miss category.
- [ ] Capture user correction.
- [ ] Append/update `intent-misses.md`.
- [ ] Recompile relevant `fde-tasks.md` guidance.
- [ ] Keep MVP weighting simple and inspectable.

Possible miss categories:

- [ ] Missing context
- [ ] Wrong audience
- [ ] Too generic
- [ ] Needs evidence
- [ ] Wrong format
- [ ] Wrong constraint
- [ ] Unsafe to automate
- [ ] Needs human checkpoint

Acceptance criteria:

- [ ] A correction made once can change subsequent Cordia behavior for the same workspace.

---

# Phase 11 — Guided Connector Setup

- [ ] Add connector setup strategy to connector manifest/schema.
- [ ] Support at least one setup mode such as OAuth or guided browser API-key setup.
- [ ] Add Lightpanda/browser setup adapter if appropriate for the chosen connector.
- [ ] Allow Cordia to prefill known email only if allowed.
- [ ] Require user to enter password/2FA directly.
- [ ] Ensure agent cannot read/store password values.
- [ ] Pause before sensitive token generation if the flow requires human confirmation.
- [ ] Capture generated token directly into encrypted secret storage.
- [ ] Return `secret_ref`/status to the agent instead of raw secret.
- [ ] Validate connector using direct API/curl after setup.
- [ ] Prefer direct runtime after browser-assisted setup.
- [ ] Destroy/expire setup browser session after completion.

Acceptance criteria:

- [ ] A nontechnical user can connect one API-key-based service without manually copying the API key into Cordia.

---

# Phase 12 — Secret Handling

- [ ] Add encrypted secret store/vault abstraction.
- [ ] Never inject raw secrets into normal LLM prompt context.
- [ ] Use `secret_ref` handles.
- [ ] Resolve secrets only at execution boundary.
- [ ] Restrict arbitrary token-bearing network calls.
- [ ] Log secret usage without logging secret values.

Acceptance criteria:

- [ ] Agent runtime can successfully execute a connector tool without ever receiving the raw API key in its visible context.

---

# Phase 13 — Browser Setup vs Durable Runtime

- [ ] Document and enforce browser-first only where setup requires it.
- [ ] Use Lightpanda/browser for login/setup/navigation/fallback.
- [ ] Use direct API/curl/MCP for repeatable runtime actions whenever possible.
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
