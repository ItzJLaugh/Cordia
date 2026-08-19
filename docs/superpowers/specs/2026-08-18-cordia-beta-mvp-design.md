# Cordia Usable Beta MVP Design

## Status

Approved product design for the first public beta implementation sequence.

This specification narrows the architecture in `docs/CORDIA_BUILD_CONTEXT.md`
and `docs/WORKSPACE_FDE_PIVOT_CONTEXT.md` into one release contract. It does
not replace those documents. Where this specification is more specific, it
records the approved beta decision.

## Product promise

Cordia turns a person's intent into a functioning, connected AI workspace and
lets that person carry the same workspace onto their computer.

The beta succeeds when a new user can complete this journey without developer
assistance:

```text
create and verify account
        ↓
talk naturally with the Cordia Agent as their FDE
        ↓
inspect and refine what Cordia understood
        ↓
generate and save a personalized workspace
        ↓
ask the Cordia Agent to create a skill or connect a system
        ↓
authorize the required connector/API safely
        ↓
run a real skill and see an evidence-backed workspace update
        ↓
log out and recover the same workspace
        ↓
download and install Cordia Desktop for Windows
        ↓
sign in and load the same cloud-authoritative workspace
        ↓
add and run one local capability through the same Cordia gateway
```

Source code, isolated component tests, or an installer artifact alone do not
satisfy this contract. The complete journey must work in a clean environment
and on the public beta deployment.

## Primary product rule: the Cordia Agent is the FDE

The Cordia Agent is not a chat widget beside an FDE system. The Cordia Agent
is the user's agentic Forward Deployed Engineer.

The user communicates desired outcomes to the Cordia Agent. The agent:

1. understands the requested outcome using the user's Surveyor profile,
   compiled FDE mission, workspace state, and prior intent corrections;
2. identifies an existing skill or designs a new declarative skill;
3. identifies the required connectors, APIs, MCP servers, or local tools;
4. explains what must be connected and why in nontechnical language;
5. opens a bounded setup or authorization surface when human input is needed;
6. requests ALLOW, ASK, or DENY decisions before execution;
7. invokes only typed capabilities through Cordia's gateway;
8. converts safe structured results into workspace artifacts and views;
9. records provenance, outcome, and any subsequent intent miss; and
10. improves the workspace without creating a second source of truth.

Users do not manually assemble connector manifests, capability schemas, agent
graphs, or skill definitions. Advanced users may inspect those structures in
Alidora, but the main Cordia experience remains conversation-led.

Buttons may accelerate an already-defined action, but clicking a button is not
a skill. A skill describes a meaningful human outcome the Cordia Agent can
reason about and execute.

## Product boundaries

### Surveyor

Surveyor is the Cordia Agent's conversational intake stage. It learns the
person's goals, responsibilities, systems, preferences, constraints, approval
style, and examples. Surveyor is not an exam, score, certification, or
CordiaAIE course.

Surveyor produces and refines:

- `operator.md`
- `connectors.md`
- `intent-misses.md`
- `fde-tasks.md`
- `permissions.md`
- `workspace-plan.md`

The source and compiled artifacts remain inspectable. The user sees a
non-scored assessment of what Cordia understands and can correct it before or
after workspace generation.

### CordiaAIE

CordiaAIE is a separate certification and course product governed by industry
compliance standards. CordiaAIE scoring, rubrics, course state, and
certification outcomes must not silently influence Surveyor, the Cordia Agent,
or workspace behavior.

Any future bridge between CordiaAIE and Cordia requires its own explicit,
inspectable contract and user-visible consent.

### Alidora

Alidora is Cordia's advanced Agentic System Builder. Cordia builds the body of
the workspace; Alidora exposes and eventually edits the internal agentic
system behind that workspace.

For this beta, Alidora remains a read-only, non-primary projection of the same
canonical workspace state. It may not own separate state, permissions,
connectors, secrets, execution, or outcomes. Authoring and execution in
Alidora remain outside the intake-to-desktop beta acceptance path.

## Chosen architecture

The beta uses a universal vertical-slice architecture.

The existing Surveyor pipeline, Markdown artifacts, compiler, canonical cloud
workspace, permission engine, vault, skill registry, React workspace, and
Electron bridge are extended in place. No parallel connector system,
workspace store, desktop workspace, or agent runtime is introduced.

```text
Cordia account and session
        ↓
Cordia Agent / Surveyor conversation
        ↓
source artifacts → compiled FDE artifacts
        ↓
canonical cloud workspace state
        ↓
Cordia Agent plans skill or connector need
        ↓
Cordia capability gateway
        ↓
permission → secret resolution → typed adapter
        ↓
safe result → artifact/view mutation → provenance
        ↓
same state rendered by web and Cordia Desktop
```

The architecture deliberately rejects two alternatives:

- Building many bespoke provider integrations before the shared gateway would
  delay the usable beta and duplicate setup, secret, permission, audit, and
  rendering behavior.
- Treating unrestricted Desktop or browser automation as universal integration
  would be fragile and would bypass the typed capability and permission model.

## Canonical workspace and continuity

The cloud workspace remains authoritative for the beta.

It owns:

- source and compiled artifacts;
- windows and artifact projections;
- connector lifecycle and runtime status;
- skills and capability references;
- ALLOW, ASK, and DENY policy;
- context sources;
- automations when implemented;
- mutations and provenance;
- account entitlement and usage state; and
- registered desktop devices and their safe capability summaries.

Web and Desktop render the same workspace identifier and revision. Desktop
does not create an alternate local workspace store. Local path mappings,
device keys, and OS-specific capability details remain device-local and are
represented in cloud state only by opaque identifiers, safe labels, bounded
availability, and provenance.

Every canonical mutation has:

- authenticated account ownership;
- expected workspace identifier;
- expected prior revision or equivalent conflict guard;
- mutation type and bounded payload;
- actor and source;
- resulting revision; and
- provenance/audit metadata.

The beta is online-required. If cloud state cannot be reached, Desktop shows a
bounded unavailable state and does not treat stale local data as authoritative.
Offline-first merge and conflict resolution are not part of this beta.

## Universal connector framework

Cordia's universality comes from one connector contract, not from claiming
that every provider already has a bespoke adapter.

Any service with an API, MCP server, or local programmatic interface can be
added without changing the Cordia Agent or workspace architecture. A service
without a usable programmatic interface may be represented as planned or
manual, but must never appear live.

### Connector paths

The framework supports four paths:

1. **Built-in provider connector** — a reviewed Cordia adapter for a known
   provider.
2. **Guided API connector** — OAuth 2, API key, or another declared auth mode
   plus an OpenAPI schema or bounded manually described operations.
3. **Remote MCP connector** — an authenticated remote MCP endpoint whose tools
   are imported only after schema and policy validation.
4. **Desktop/local connector** — a local repository, local MCP server, or
   another explicitly selected local capability exposed by Cordia Desktop.

Browser assistance may help a user complete setup when a provider requires
login, consent, or token generation. Stable runtime operations use direct API,
MCP, CLI, or local typed adapters whenever possible. Browser automation does
not become the default durable runtime.

### Connector manifest

Each connector record contains only bounded declarative metadata:

```json
{
  "id": "provider_or_user_scoped_id",
  "name": "Human-readable name",
  "kind": "builtin|api|mcp|local",
  "implementation_status": "live|planned",
  "lifecycle": "PROPOSED|IN_PROGRESS|LIVE|FAILED|DECLINED|NEEDS_HANDOFF",
  "setup_strategies": ["oauth2|api_key|guided_browser|mcp|desktop"],
  "runtime_transports": ["direct_api|mcp|local_bridge"],
  "capability_ids": ["typed.capability"],
  "skill_ids": ["human_outcome_skill"],
  "view_modes": ["dash|derived|live"],
  "permission_defaults": {"typed.capability": "ALLOW|ASK|DENY"},
  "secret_refs": ["opaque_reference_only"],
  "runtime_status": "not_observed|live|needs_attention|unavailable"
}
```

Raw credentials, provider payloads, local paths, prompts, and authorization
headers are never stored in the manifest.

### Connector setup led by the Cordia Agent

The user asks the Cordia Agent for an outcome. If the required connector is
missing, the agent proposes it in plain language and explains:

- what service is required;
- what Cordia needs to read or change;
- whether the connection is built-in, API, MCP, or local;
- which permissions will be ALLOW, ASK, or DENY;
- what the user must authorize; and
- what will become visible in the workspace.

The setup surface then gathers only the human input required for that step.
Passwords and 2FA remain in the provider-owned or isolated setup surface. API
keys and tokens are sent directly to encrypted secret storage and replaced by
opaque `secret_ref` values before the Cordia Agent can continue.

After setup, Cordia validates the connection using a bounded read or health
operation. Only successful validation may transition the connector to `LIVE`.
Failure results in `FAILED` or `NEEDS_HANDOFF` with safe recovery guidance.

### Capability gateway

The Cordia capability gateway is the only execution entrance used by the
Cordia Agent. It is not the dashboard and it does not own presentation state.

For every call it must:

1. validate the authenticated account, workspace, connector, skill, and typed
   capability;
2. confirm connector lifecycle and runtime availability;
3. evaluate ALLOW, ASK, or DENY;
4. create a durable approval checkpoint for ASK and stop before execution;
5. reject DENY without reading secrets;
6. reserve usage entitlement before a cost-bearing operation;
7. resolve a secret only inside the approved adapter boundary;
8. call a fixed typed adapter with a validated payload;
9. bound and sanitize the structured result;
10. commit or release the usage reservation according to the result;
11. write safe audit and provenance events; and
12. return a safe result for the Cordia Agent and workspace renderer.

The agent never receives raw credentials in its prompt or visible tool result.
Unknown connectors, capabilities, fields, transports, and permission states
fail closed.

### Beta universality proof

The beta must prove the shared contract with three distinct paths:

- the existing GitHub read adapter as a real cloud connector;
- one user-defined API or remote MCP connector created without changing core
  Cordia code; and
- one Desktop/local connector using the same capability and permission model.

GitHub is evidence that the framework works, not Cordia's product boundary.

## Skill creation and execution

A skill is a declarative, inspectable human outcome. The Cordia Agent may
select an existing skill or draft a new one from conversation.

A generated skill contains:

- stable identifier and human-readable purpose;
- evidence linking it to the user's request and FDE mission;
- required connector and capability identifiers;
- typed input and bounded result schemas;
- default permission and approval checkpoints;
- artifact/view mutation behavior;
- failure and recovery behavior; and
- provenance requirements.

Generated skills are validated before registration. A skill cannot contain raw
secrets, arbitrary shell strings, unbounded network destinations, hidden local
paths, or generic execution payloads. A skill that requires an unavailable
connector remains proposed and leads the Cordia Agent into connector setup.

The beta must demonstrate:

- an existing real skill selected by the Cordia Agent;
- a new bounded skill created through conversation;
- connector setup initiated because that skill requires it;
- ALLOW execution;
- a durable ASK pause and explicit resume;
- a DENY result that never reaches the adapter; and
- a safe visible artifact or DashView update with provenance.

## Workspace presentation

The primary workspace remains:

- a full-height Cordia Agent on the left;
- agent-built artifact windows on the right; and
- a bottom inspection dock for Connected, Skills, Access, Context, Activity,
  and Automations.

Workspace windows are artifacts built by the Cordia Agent, not embedded copies
of external applications.

- **DashView** is the default bounded native projection.
- **DerivedView** combines safe results from multiple sources.
- **LiveView** is available only when the connector explicitly supports it and
  the user explicitly enables it.

Clicking a skill control inserts and immediately executes the corresponding
bounded intent through the Cordia Agent, but the same action remains available
through natural conversation. UI controls never bypass the agent runtime,
permissions, usage gate, or audit trail.

The builder and runtime use the same canonical renderer. There is no separate
mock builder that produces a different final workspace.

## Identity and new-user intake

The beta supports open self-service registration.

Required behavior:

- email verification creates a verified account;
- sign-in and session recovery work on web and Desktop;
- existing-account registration never claims to send a verification code when
  it only sends a security notification;
- successful authentication resumes the latest saved workspace when one
  exists, otherwise it resumes Surveyor;
- account ownership scopes every profile, workspace, connector, secret,
  approval, usage, billing, device, and audit record;
- logout clears authenticated browser identity without deleting saved cloud
  state; and
- Desktop sign-in retrieves the same account-owned workspace.

Surveyor onboarding is included and capped at twelve user conversation turns
for the beta. The Cordia Agent must use those turns efficiently, show progress,
allow correction, and compile a usable initial workspace without requiring the
user to understand the underlying artifacts.

## Usage controls and billing

The public beta must have server-side cost controls before open registration is
advertised.

### Free entitlement

One verified account receives:

- Surveyor onboarding, up to twelve user turns;
- one initial workspace compilation/generation; and
- ten lifetime cost-bearing Cordia Agent actions.

Viewing, navigation, artifact inspection, connector status checks, account
settings, and other deterministic non-model reads do not consume an action.
An operation that fails because of Cordia infrastructure or provider
unavailability does not consume an action.

### Starter subscription

- Price: USD 29 per month.
- Allowance: 100 cost-bearing actions per billing month.
- Hard stop at the allowance; no automatic overage.
- Unused actions do not roll over.
- The price identifier and allowance are server configuration, not trusted
  browser values.

### Enterprise

The pricing surface shows Enterprise as `Coming soon`. It has no checkout,
fake availability, or implied enterprise controls in the beta.

### Stripe boundary

Stripe-hosted Checkout collects payment details. Cordia never receives or
stores card data.

Cordia creates Checkout sessions using fixed server-side price configuration,
verifies signed Stripe webhooks, and derives account entitlement from durable
billing records. Return URLs are presentation only and do not grant access.

Cancellation or payment failure preserves the user's workspace and moves the
account to its valid remaining entitlement. It never deletes artifacts,
connectors, or Desktop state.

### Usage ledger

Usage is account-scoped and shared by web and Desktop. Reinstalling Desktop,
clearing browser storage, creating another workspace, or replaying a request
cannot reset or duplicate entitlement.

Cost-bearing execution uses a reservation model:

```text
authenticate and authorize
        ↓
idempotently reserve one action
        ↓
execute the bounded model/capability operation
        ↓
commit on valid user-visible completion
or release on Cordia/provider failure
```

The same idempotency key cannot create multiple charges or multiple committed
actions. The user sees remaining actions and a clear upgrade path before the
hard stop.

The service also enforces per-account rate limits and a global configurable
provider-spend circuit breaker. When the breaker is open, cost-bearing actions
stop safely while deterministic workspace access remains available.

## Cordia Desktop beta

### User-facing installation

The primary Windows installation is a normal `.exe` package built from the
existing Electron application using a deterministic Windows installer target.
The package is code-signing-ready. A signed package is required before broad
public distribution; an unsigned build may be used only for a clearly labeled
private beta because Windows may show SmartScreen warnings.

`install.ps1` remains an optional administrator/developer bootstrapper that
verifies and launches the packaged installer. It is not the normal user flow
and it never generates a second workspace or grants machine-wide capabilities.

The web workspace displays `Install Cordia Desktop` only after a canonical
workspace has been saved. The download metadata includes a fixed release,
cryptographic checksum, supported architecture, and minimum Windows version.

### Desktop session and workspace

After installation:

1. Cordia Desktop opens the Cordia sign-in flow.
2. The user signs in with the same verified account.
3. Desktop loads the latest account-owned workspace from Cordia Cloud.
4. The same Cordia Agent, artifacts, windows, dock, connectors, skills, and
   permissions render through the same production workspace surface.
5. Mutations save to canonical cloud state and become visible on web reload.

Desktop uses the existing hardened Electron posture:

- renderer sandbox enabled;
- context isolation enabled;
- Node integration disabled;
- fixed Cordia cloud origin and bounded development override;
- new browser windows denied unless an exact approved authorization flow
  requires an external system browser;
- fixed IPC channels only; and
- no renderer-supplied shell commands, paths, URLs, or arbitrary operations.

### Device registration and local bridge

Desktop registers an opaque device identifier and device public credential.
Private device material remains protected by the operating system. Revoking a
device disables its cloud-advertised local capabilities without deleting the
workspace.

The local bridge:

- discovers only user-selected or explicitly enabled capabilities;
- keeps absolute paths and raw local configuration on the device;
- reports safe labels, opaque identifiers, typed capability availability, and
  health to Cordia Cloud;
- exposes local capabilities through the same gateway contract;
- enforces ALLOW, ASK, and DENY locally immediately before execution; and
- returns bounded structured results with provenance.

The first local proof uses the existing repository/Git foundation. A beta user
must also be able to register a local MCP connector through the universal
connector path. Unrestricted filesystem, shell, PowerShell, Docker, package
installation, deployment, and credential access remain unavailable unless a
future typed capability explicitly defines and secures them.

## Error and recovery behavior

All public errors use bounded user-facing states and retain recoverable user
input where safe.

- Authentication failure never leaks whether protected account data exists.
- Surveyor/model failure retains the user's draft and does not consume an
  action.
- Workspace revision conflict refreshes canonical state and asks the user to
  retry; it does not silently overwrite newer state.
- Connector setup failure retains no raw secret in the browser or logs and
  provides safe retry or handoff guidance.
- Connector runtime failure marks bounded runtime health without erasing the
  configured connector.
- ASK checkpoints survive refresh/re-login and can be approved, declined, or
  expired exactly once.
- DENY never reads a secret or invokes an adapter.
- Usage exhaustion leaves deterministic workspace access available and offers
  the real Starter checkout.
- Stripe or webhook failure does not grant entitlement and does not destroy
  existing work.
- Desktop cloud outage does not mutate stale local state as authoritative.
- Installer failure provides a checksum/retry path and leaves the web
  workspace usable.

Raw exception text, credentials, ciphertext, provider response bodies, local
paths, authorization URLs with tokens, and internal prompts never enter public
errors, artifacts, chat receipts, or audit payloads.

## Security requirements

- All state-changing routes require authenticated account ownership.
- Connector and skill execution fail closed on unknown identifiers or schema
  fields.
- Network adapters use declared HTTPS origins and defend against SSRF, private
  network targets, redirect escapes, and DNS rebinding.
- OAuth state, PKCE, callback origin, and expiration are validated.
- Webhook signatures and replay windows are validated.
- API and MCP operations use bounded timeouts, response sizes, and schemas.
- Secrets are encrypted at rest and resolved only inside the approved adapter
  boundary.
- Agent-visible inputs and outputs contain no raw secrets.
- Desktop IPC uses fixed channels and fixed operations.
- Local paths never cross to cloud state or prompts.
- ASK approvals bind account, workspace, device when relevant, connector,
  capability, arguments digest, expiration, and one-use decision.
- Usage reservations and billing webhooks are idempotent.
- Audit events contain identifiers and bounded outcomes, never secret values or
  arbitrary provider payloads.

## Verification strategy

Each release unit follows test-driven development and receives an independent
review before integration.

### Contract tests

- Connector manifests reject unknown, secret-shaped, path-shaped, and
  unbounded fields.
- Every live connector maps to registered capabilities, skills, permissions,
  health, projections, and adapter contracts.
- API, MCP, and local connectors pass the same gateway conformance suite.
- ALLOW, ASK/resume, DENY, secret isolation, audit, and result bounding are
  proven at route level.
- Generated skills fail closed unless every referenced connector, capability,
  schema, and permission exists.

### Journey tests

- New account verification → Surveyor → assessment → workspace generation.
- Logout/login → exact account-owned workspace recovery.
- Cordia Agent requests a connector because a requested skill requires it.
- Successful connector setup → typed skill execution → visible artifact
  update.
- Intent correction → recompilation → subsequent runtime guidance.
- Free action exhaustion → hard stop → Stripe Checkout → webhook entitlement →
  restored action availability.
- Web mutation → Desktop refresh and Desktop mutation → web refresh with the
  same workspace revision chain.

### Desktop and release tests

- Windows CI produces a deterministic installer and checksum.
- Installer runs on a clean supported Windows environment.
- Installed app uses production security settings.
- Same-account sign-in loads the same workspace.
- One selected local repository capability and one local MCP connector pass the
  shared conformance tests.
- Uninstall/reinstall does not reset cloud usage or create another workspace.

### Production verification

Before calling a release live:

- merge the reviewed commit to `main`;
- preserve and reconcile Hostinger server-only configuration;
- install locked runtime dependencies;
- run preflight and database migrations;
- restart the bounded backend service;
- verify loopback and public health;
- run the public new-user journey with a test account;
- run a real connector and inspect its visible update;
- verify usage and Stripe in test mode before live billing activation;
- install the published Desktop package on a clean Windows machine;
- verify the same workspace and one local capability; and
- record exact deployed commit, installer version, and evidence.

No source-only, localhost-only, or partially deployed state may be described as
the full beta being live.

## Delivery decomposition

This architecture is delivered through independently reviewable releases. Each
release reuses the previous one and leaves the product in a testable state.

### Release 1 — Intake and cloud continuity

Close the verified-account → Surveyor → assessment → canonical workspace →
logout/login recovery journey using the existing store and workspace renderer.
Reconcile builder and runtime so the generated workspace is the workspace the
user continues using.

### Release 2 — Cordia Agent FDE and universal gateway

Make the Cordia Agent the explicit skill/connector orchestration owner. Finish
the typed capability gateway, generated-skill validation, durable ASK resume,
and one visible result loop. Route the existing GitHub adapter through the
finished contract.

### Release 3 — User-defined connector

Add agent-led API/OpenAPI and remote MCP setup, safe credential capture,
connection validation, runtime health, and native projection. Prove a new
connector can be registered without modifying core Cordia code.

### Release 4 — Usage controls and Stripe

Add the account-scoped reservation ledger, free allowance, rate limits, global
spend breaker, Starter Checkout, webhook-derived entitlement, pricing UI, and
Enterprise `Coming soon` state.

### Release 5 — Windows Desktop beta

Package the existing Electron shell as the primary `.exe`, add authenticated
device registration, load and mutate the same cloud workspace, expose the
existing local repository foundation through the shared gateway, and register
one local MCP connector.

### Release 6 — Public beta gate

Run the entire journey on the production deployment and a clean Windows
installation. Fix every blocker before inviting beta users. Publish a simple
setup and test manual only after the evidence exists.

## Explicit non-goals for this beta

- Prebuilding every commercial provider connector.
- Claiming a service is live because it appears in the catalog.
- Offline-first workspace ownership or multi-master synchronization.
- Unrestricted shell, filesystem, browser, or network execution.
- Full Alidora authoring/execution.
- CordiaAIE certification or course changes.
- Enterprise administration, team billing, or organization RBAC.
- Mobile applications.
- Usage overages or automatic action purchases beyond the Starter allowance.
- Hidden background automation that has not been explicitly configured and
  permissioned.

## Beta acceptance checklist

The beta is usable only when all items below are directly demonstrated:

- [ ] A new person can register and verify an account.
- [ ] Surveyor completes a natural, non-scored intake within the beta turn cap.
- [ ] The user can inspect and correct source and compiled understanding.
- [ ] Cordia generates and saves one canonical workspace.
- [ ] Logging out and back in recovers the same workspace.
- [ ] The Cordia Agent creates or selects a meaningful skill from conversation.
- [ ] The Cordia Agent identifies and requests the connector required by that
      skill.
- [ ] One built-in cloud connector operates through the universal gateway.
- [ ] One user-defined API or remote MCP connector can be added without a core
      code change.
- [ ] One local/Desktop connector operates through the same gateway.
- [ ] ALLOW, durable ASK/resume, and DENY are each proven on real typed actions.
- [ ] Secrets remain outside prompts, public results, artifacts, and logs.
- [ ] A real skill creates an evidence-backed visible workspace update.
- [ ] An intent correction affects subsequent same-workspace runtime guidance.
- [ ] Free usage stops after ten committed cost-bearing actions.
- [ ] Cordia-caused failures do not consume an action.
- [ ] Stripe test Checkout and signed webhook grant the Starter entitlement.
- [ ] The pricing surface shows Starter accurately and Enterprise as coming
      soon.
- [ ] A normal Windows `.exe` installs Cordia Desktop.
- [ ] Desktop sign-in loads the same account-owned workspace.
- [ ] A Desktop mutation is visible on web and a web mutation is visible on
      Desktop without creating a second workspace.
- [ ] One local capability executes with local permission enforcement and safe
      provenance.
- [ ] The complete path passes on the public deployment and a clean Windows
      machine.
