# Cordia Thin-Spine MVP Design

## Status and authority

This design records the approved smaller Cordia direction from the August 20,
2026 product discussion. It is pending written review before implementation
planning.

For the initial working Cordia journey, this document is more specific than
`docs/superpowers/specs/2026-08-18-cordia-beta-mvp-design.md`. Where the two
conflict, this design controls. The older document remains useful historical
context for capabilities that are deliberately deferred here.

The product-truth requirements in `AGENTS.md` continue to control all status,
testing, release, and deployment claims.

## Problem being corrected

Cordia accumulated useful foundations but exposed and planned too many
separate products and subsystems at once: Surveyor, assessment, builder,
interface, dashboard, registries, routing, desktop packaging, billing, and
Alidora. That made a small customer outcome look like an enterprise platform
rewrite and encouraged component-level tests to be mistaken for a working
product journey.

The correction is not a mass rewrite. Cordia will retain its proven support
code and create one thin, continuous product spine through it.

## Product promise

Cordia learns how a person thinks and works, then gives that person one
connected AI workspace operated through the Cordia Agent.

The first MVP succeeds only when this journey works:

```text
sign in
  -> complete profile calibration
  -> enter one saved workspace
  -> continue with the Cordia Agent in the same conversation
  -> ask to connect a service
  -> complete a truthful setup card
  -> run one bounded skill
  -> see an evidence-backed artifact update in the same workspace
```

Surveyor, builder, interface, and dashboard may temporarily remain as internal
routes or compatibility layers. The user experiences one Cordia workspace.

## The five core responsibilities

### 1. Workspace memory

Cordia stores the durable understanding of the person and workspace. The
authoritative source is owner-scoped structured data in the existing database.
Cordia compiles that data into a Markdown memory artifact for the model and for
human inspection.

The Markdown is a logical `memory.md` artifact, not a user-machine filesystem
file and not a second state owner.

### 2. Real Cordia Agent

One configured model continues the conversation after profile calibration.
The Cordia Agent is the user's conversational FDE. It reads the compiled
workspace memory and current artifact state before each turn.

If the model is not configured or a call fails, Cordia says so plainly. A
deterministic fallback may keep navigation and saved data available, but it may
not pretend to understand, propose, connect, create, or execute anything.

### 3. Structured agent actions

Model text is untrusted. Each turn returns exactly one validated envelope of
one of these kinds:

1. `speak`
2. `propose_connector`
3. `create_artifact`
4. `propose_skill`
5. `run_approved_skill`

`speak` contains only the user-visible reply. The other envelopes contain a
bounded user-visible reply plus one proposal. The model may propose intent.
Deterministic Cordia code validates identifiers, schemas, permissions,
connector availability, secret boundaries, and workspace ownership before
anything changes.

### 4. Universal connector path

Cordia's product boundary is not a list of prebuilt providers. The initial
generic connector contract supports:

- API key plus a bounded test request;
- OpenAPI URL import; and
- authenticated remote MCP connection.

The existing GitHub connector remains the built-in example. OAuth-only
providers such as Google Drive require provider-specific OAuth setup later and
must be described as unavailable until that setup exists. Cordia never implies
that catalog presence means a connector is functional.

### 5. Artifact workspace

Agent output becomes artifact windows in the existing React workspace.

- **DashView** is the default safe native projection.
- **DerivedView** combines bounded results from multiple sources.
- **LiveView** appears only when the connector supports it and the user has
  explicitly enabled it.

The Cordia Agent remains on the left. Artifact windows occupy the primary
workspace on the right. A skill result visibly updates one of those artifacts.

## Profile calibration contract

The external four-part survey becomes Cordia's profile-calibration input. It
replaces the current scored profiling questionnaire for the MVP; it does not
replace the Cordia Agent's operational conversation.

The four evidence classes are:

1. personality observations;
2. domain knowledge and calibration;
3. explicit communication choices; and
4. natural examples of requests the person would actually send to an AI.

The survey implementation may remain separately hosted. Cordia depends only
on a versioned result contract, never on page scraping. The minimum accepted
shape is:

```json
{
  "schema_version": "cordia-profile-v1",
  "survey_version": "provider-version",
  "profile_id": "opaque-provider-id",
  "communication": {
    "explicit_implicit": 9.0,
    "detail_big_picture": 2.0,
    "indirect_direct": 10.0,
    "reasoning_before_conclusion": true,
    "infer_unstated_context": true
  },
  "domains": [
    {
      "id": "technology_software",
      "self_rating": 5,
      "calibration": "consistent"
    }
  ],
  "personality": {},
  "natural_requests": [],
  "completed_at": "ISO-8601 timestamp"
}
```

Exact optional fields may expand only through a new schema version. Unknown
fields fail closed at import rather than silently entering memory or a model
prompt.

Cordia needs the survey engineer to provide only:

- one canonical example payload;
- stable field definitions and score ranges;
- `survey_version` semantics;
- a completion callback, webhook, or result-retrieval endpoint; and
- a secure way to bind the result to an opaque Cordia profile.

Full survey source code is not an MVP integration requirement. It becomes
necessary if Cordia absorbs the survey, independently validates the scoring,
or makes public scientific-validity claims.

## Memory compilation

Cordia stores the imported structured result and compiles a short model-facing
artifact. Numerical scores are not repeated in every model prompt when a
bounded behavioral instruction is sufficient.

Natural requests from the survey are stored as profile evidence and initial
workspace intent. They do not masquerade as prior chat messages or as commands
that have already been approved.

```md
# Workspace Memory

## Communication policy
- Use high-context explanations.
- Infer likely unstated needs, but label assumptions.
- Explain reasoning before conclusions.
- State material concerns directly.

## Domain context
- Technology and software: advanced familiarity.
- Work and professional systems: strong familiarity.
- Explain uncertain or unfamiliar concepts without assuming knowledge.

## Observed workspace intent
- Understand system dependencies.
- Identify operational risks.
- Analyze evidence before recommending changes.
- Connect engineering systems into one visible workspace.

## Evidence
- Source: Cordia Profile Calibration
- Survey version: provider-version
- Profile schema: cordia-profile-v1
```

Profile evidence changes presentation and communication. It never changes
facts, permissions, connector access, approval requirements, or security
policy.

## One continuous user experience

After authentication:

- a user without calibration is sent into profile calibration;
- a calibrated user without a workspace receives one canonical workspace;
- a returning user resumes their latest canonical workspace; and
- every path lands in the same primary Cordia workspace surface.

The initial Cordia Agent message acknowledges relevant memory and asks what the
person wants to accomplish. Operational discovery happens naturally in that
conversation. It is not another twelve-turn survey.

The separate Surveyor, builder, interface, and dashboard pages may continue to
serve compatibility routes during migration, but new navigation must not send
the user through them as separate products.

## Agent turn contract

One authenticated workspace-turn endpoint receives:

- workspace identifier;
- expected workspace revision;
- user message; and
- idempotency key.

The server loads owner-scoped memory, bounded recent conversation, connector
truth, skills, and safe artifact summaries. The model returns speech and at
most one proposed action. Cordia validates the action before registration,
execution, or mutation.

The public result contains only:

- assistant speech;
- a bounded action state;
- safe identifiers;
- approval or setup requirements; and
- the resulting workspace revision when it changes.

Raw prompts, secrets, provider payloads, local paths, internal exceptions, and
unvalidated model fields never cross this boundary.

## Connector flow

When the user says `Connect X`, the hop-by-hop behavior is:

1. The agent identifies the desired human outcome.
2. The agent proposes a connector kind and required access.
3. Deterministic code validates the proposal against the three supported
   generic paths or a built-in connector.
4. The workspace renders a setup card containing only the missing human input.
5. Credentials go directly to the existing encrypted vault and become opaque
   references before the agent continues.
6. Cordia runs a bounded connection test.
7. Only a successful real test marks the connector available.
8. The agent proposes or selects a bounded skill using that connector.
9. The existing capability gateway enforces ALLOW, ASK, or DENY.
10. A safe result becomes an artifact update with provenance.

For an unsupported OAuth-only service, Cordia explains that the OAuth setup is
not yet implemented. It may create a planned connector proposal, but it may
not display a connected or live state.

## Skill contract

A skill is a small declarative human outcome, not generated executable code.
It identifies:

- purpose;
- evidence from the user's request;
- required connector and typed operation;
- bounded inputs and outputs;
- permission requirement;
- artifact projection; and
- safe failure guidance.

The MVP does not add a second skill registry. Generated skills use the existing
skill resolution and capability gateway after validation. Arbitrary shell,
arbitrary URLs, hidden prompts, raw secrets, and unbounded payloads are not
valid skill fields.

## Existing code disposition

### Retain and use

- authentication and account ownership;
- PostgreSQL profile, conversation, secret, and workspace persistence;
- existing Markdown artifact storage and compilation;
- the existing environment-driven model call in `training_backend.py` and the
  live/limited selection seam in `llm.py`, extracted into a focused provider
  module during Sprint 2;
- the vault and opaque secret references;
- capability permissions and gateway;
- GitHub adapter as one connector example;
- canonical workspace state; and
- the React artifact workspace and Electron shell foundation.

### Adapt in place

- import profile calibration into the existing owner-scoped profile record;
- compile one concise `memory.md` artifact;
- route workspace chat through the five-action contract;
- let existing workspace state receive validated artifact mutations; and
- make the current React workspace the only primary user surface.

### Bypass during the MVP

- the current multi-stage Surveyor scoring and recommendation path;
- visible builder/interface/dashboard handoffs;
- broad FDE registry and routing work not required by the direct loop;
- prebuilt catalog claims for unverified connectors; and
- any duplicate state, permission, connector, skill, or execution system.

Bypassed code is not deleted during the first four sprints. Removal happens
only after the continuous journey is working and tests prove the compatibility
paths are unused.

### Keep separate or defer

- CordiaAIE courses, certification, scoring, and compliance;
- Alidora authoring and execution;
- billing and subscription enforcement;
- broad Desktop distribution and local capability expansion;
- enterprise controls;
- background automations; and
- provider-specific OAuth integrations.

Alidora may later inspect and edit the internal agentic system behind the same
canonical workspace. It does not own a second memory, connector, permission,
secret, skill, or execution system.

## Delivery in four sprints

### Sprint 1: Profile memory and continuity

**Outcome:** A signed-in user imports a valid profile-calibration result and
enters one workspace where the Cordia Agent can read the compiled memory.

**Work:** Define the importer, validate and store the structured result,
compile `memory.md`, create or recover one canonical workspace, and route the
user into the primary workspace.

**Evidence:** Contract tests using the observed result shape, owner-isolation
tests, memory snapshot tests, and an actual-app browser journey. The separately
hosted callback remains `unverified` until its endpoint exists.

### Sprint 2: Real Agent and five actions

**Outcome:** The user continues the conversation with one real model and sees
truthful proposed action states.

**Work:** Load memory into the existing model boundary, define the five-action
schema and validator, and route the existing workspace conversation through
it. Limited mode cannot manufacture actions.

**Evidence:** Parser and ownership tests, one local integration journey, and
one real-provider call using configured credentials.

### Sprint 3: Connector, skill, and artifact loop

**Outcome:** The user requests a connector, completes setup, runs one approved
skill, and sees one safe artifact update.

**Work:** Implement the smallest complete generic connector path first, then
apply the same contract to the remaining generic paths without adding another
gateway. Reuse vault, permissions, skills, workspace state, and renderer.

**Evidence:** Contract tests plus one real non-GitHub connector. The provider
credential is requested only at the real setup boundary.

### Sprint 4: Continuous journey and release candidate

**Outcome:** A new user experiences one uninterrupted Cordia product from
sign-in through a working connected artifact.

**Work:** Remove visible handoffs, recover the same workspace after sign-in,
prove error recovery, and reconcile authority documentation. Do not add
billing, broad Desktop packaging, or Alidora authoring.

**Evidence:** Full actual-app journey, real model, real connector, visible
artifact update, reload recovery, independent review, and later a separately
authorized production deployment verification.

## Error and truth behavior

- Missing or failed model: state that the Cordia Agent is unavailable; retain
  saved workspace access.
- Missing survey endpoint: allow a controlled development import, but do not
  call the external survey integrated.
- Invalid profile result: save nothing and return bounded correction guidance.
- Connector setup failure: retain no raw credential in browser, transcript,
  memory, artifact, or log.
- Unsupported OAuth provider: describe the missing setup honestly.
- ASK: pause before secret resolution or adapter execution.
- DENY: do not read the secret or invoke the adapter.
- Provider failure: show a bounded recovery state and do not fabricate an
  artifact update.
- Unknown action, connector, capability, skill, field, or view mode: fail
  closed.

## Evidence labels

Every sprint reports outcomes using these labels:

- **Built** — source exists.
- **Verified locally** — deterministic tests or a local actual-app journey
  passed.
- **Verified with real provider** — the exact external provider path worked.
- **Verified live** — the claimed public deployed journey was directly tested.
- **Not yet verified** — the required evidence does not exist.

A lower evidence level never implies a higher one.

## External inputs required at exact boundaries

Implementation proceeds without asking the product owner for technical design
decisions. Human input is required only when an external boundary is reached:

1. survey result endpoint or canonical result payload from the survey engineer;
2. one model-provider credential entered through the approved secret channel;
3. one real non-GitHub connector credential or MCP endpoint entered through
   Cordia's setup surface; and
4. explicit authorization before merging or deploying a coherent release.

## Scope and size discipline

The design intentionally does not impose a misleading total line-count target.
Each sprint must use the fewest existing modules that make its user outcome
real. A new abstraction is rejected unless it removes a duplicate state owner
or is required for one of the five core contracts.

Thirty to sixty minutes is sufficient for specification and implementation
planning, not for honest real-provider and production verification. The four
sprints remain small and independently testable, and none requires building
the previously planned enterprise platform first.

## Acceptance gate

The thin-spine MVP is complete only when one test user can directly demonstrate:

- profile calibration stored and compiled into inspectable workspace memory;
- the same Cordia Agent conversation continuing in the primary workspace;
- a real configured model or an honest unavailable state;
- an agent-proposed connector setup;
- one real verified non-GitHub connector;
- conformance evidence for API-key/test, OpenAPI-import, and remote-MCP setup
  contracts, even when only one is exercised against a real external service;
- one validated skill executed through the existing gateway;
- one evidence-backed artifact visibly updating;
- the same workspace recovering after sign-out and sign-in; and
- no false claim that unsupported connectors, OAuth, LiveView, Alidora,
  Desktop, billing, or production deployment are complete.
