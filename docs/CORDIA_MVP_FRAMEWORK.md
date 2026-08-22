# Cordia MVP Framework

**Status:** Canonical MVP authority pending implementation-plan approval

**Approved direction:** August 22, 2026

**Purpose:** Reduce Cordia to one complete user journey and one small executable kernel.

## 1. Authority

This document defines what must work before Cordia may be called a functional
beta MVP. `CORDIA_BUILD_CONTEXT.md` remains the long-term product authority.
The thin-spine design remains useful implementation evidence. When older plans
compete for development priority, this document controls MVP sequencing.

This framework adapts existing authentication, PostgreSQL state, vault,
workspace, agent, connector, permission, artifact, and desktop code. It must not
create parallel replacements for those systems.

## 2. Product outcome

A real user must be able to complete this journey:

```text
Create account
  -> complete the research-backed survey
  -> save human-readable workspace memory
  -> enter one continuous Cordia workspace
  -> converse with a real OpenAI-backed Cordia Agent
  -> ask to connect a tool
  -> complete a truthful setup card
  -> verify and save the connection securely
  -> receive a proposed artifact and skill
  -> approve and run the skill
  -> see the real result update the artifact
  -> reopen the same workspace
  -> install Cordia on Windows
  -> access the same working workspace from the desktop app
```

No component test, mock adapter, catalog entry, or UI card substitutes for this
observed journey.

## 3. The kernel

The MVP kernel has six responsibilities.

### 3.1 Workspace

One owner-scoped canonical object contains:

```text
id
owner
revision
memory
conversation
connectors
artifacts
skills
pending_actions
usage
```

PostgreSQL structured data is authoritative. `memory.md` is a compiled,
human-readable artifact of survey/profile truth, never a filesystem state owner.
All user and agent changes use the same compare-and-save revision boundary.

### 3.2 Model provider

The provider receives bounded workspace memory, recent conversation, and the
allowed action schema. It returns exactly one structured Cordia action.

The beta has one real provider: OpenAI through Cordia's server. The Cordia API
key never enters browser code or the desktop executable. The provider interface
remains small enough for later Anthropic, Gemini, and local-model adapters, but
those adapters do not block the beta.

Provider failure is visible and fixed: Cordia states that the model is
unavailable and performs no action. A failed provider call does not consume a
free action.

### 3.3 Agent action

The only action kinds are:

```text
speak
propose_connector
create_artifact
propose_skill
run_approved_skill
```

Each kind has an exact schema. Unknown fields fail closed. Action outcome copy
is deterministic and derived from verified state; provider prose cannot claim
that Cordia connected, executed, approved, or completed something.

### 3.4 Connector

A connector record contains:

```text
id
display_name
setup_kind
credential_ref
operations
status
last_verified_at
last_error_code
```

The initial universal setup kinds are:

- API key plus bounded HTTPS test request;
- HTTPS OpenAPI document import; and
- remote HTTPS MCP connection.

GitHub remains a native example, not the product boundary. OAuth-only services
require a provider-specific OAuth adapter later and must not be represented as
universally supported before that adapter exists.

Credentials are accepted only by the setup boundary, sealed before storage,
resolved only inside an approved operation, and never enter prompts, workspace
state, transcripts, artifacts, logs, or public responses.

### 3.5 Artifact

An artifact is a workspace window with:

```text
id
title
purpose
connector_id
source_operation
provenance
view_mode
safe_data
status
updated_at
```

DashView is the default. It presents bounded, renderer-safe data produced by
Cordia. LiveView appears only when the connector supports it and the user has
explicitly enabled it. An unavailable or failed source displays an honest
recovery state instead of stale or fabricated success.

### 3.6 Skill

A generated skill contains:

```text
id
name
connector_id
operation_id
input_schema
permission
artifact_id
status
```

A skill may invoke only an operation declared by the currently verified
connector. ALLOW, ASK, and DENY are enforced immediately before execution.
ASK requires a user decision and does not silently continue. The result is
projected into its artifact through the canonical workspace transaction.

## 4. Runtime flow

```text
Authenticated message
  -> owner-load canonical workspace
  -> enforce free-action allowance
  -> compile bounded model context
  -> call configured OpenAI provider
  -> validate one exact action
  -> apply deterministic permission/state rules
  -> execute nothing unless the action is approved and executable
  -> compare-and-save canonical workspace once
  -> return safe speech, action receipt, and revision
  -> refresh the visible workspace once
```

Connector setup is a separate credential boundary. Skill execution is a
separate approval boundary. Neither is hidden inside the model call.

## 5. Usage policy

Cordia automatically provides beta model usage. A free account receives ten
successful model-backed agent turns. The counter is owner-scoped and changed
server-side in the same transaction as the accepted turn.

- Authentication, survey completion, workspace loading, setup-form display,
  deterministic validation errors, and failed model calls do not consume turns.
- A successful provider response accepted as one Cordia action consumes one
  turn, whether it speaks or proposes an action.
- Duplicate idempotency keys return the prior result without consuming again.
- At the limit, Cordia preserves the workspace and displays a fixed upgrade
  message. Payment implementation is not required to prove the kernel.

## 6. Desktop boundary

The Windows app is a Cordia workspace client, not a bundled cloud API key and
not necessarily a local model.

The cloud owns authentication, canonical workspace state, managed model calls,
and usage limits. The desktop owns the window, operating-system integration,
explicit local-resource selection, OS-keychain storage for future user-owned
credentials, and the narrow local connector bridge. Local capabilities require
the same typed operation and approval rules as cloud capabilities.

Ollama or LM Studio may later implement the same model-provider contract. Local
inference and offline operation are not MVP requirements.

## 7. Existing-code disposition

### Reuse

- account/session authentication;
- PostgreSQL owner-scoped store and revision handling;
- vault/secret references;
- compiled workspace memory;
- five-action Cordia Agent contract;
- capability and permission gateway;
- canonical React workspace and DashView;
- Electron shell and narrow local bridge foundations.

### Simplify

- expose one continuous workspace instead of separate Surveyor, builder,
  interface, and dashboard products;
- configure one real OpenAI provider before adding a provider picker;
- use one connector manifest and operation contract;
- use one artifact renderer registry;
- keep deterministic action copy instead of semantic prose policing.

### Bypass temporarily

- legacy builder/interface pages that remain necessary for compatibility;
- provider catalogs without verified adapters;
- generalized automation and marketplace surfaces;
- advanced visual customization.

### Remove later

- duplicate state projections after migration is proven;
- dead mock-success branches;
- obsolete pages no longer used by the canonical journey;
- compatibility code with no remaining stored-data consumer.

Removal happens only after the canonical journey and migration evidence prove
the older path is unused.

## 8. Explicit non-goals

These do not block the beta:

- Anthropic, Gemini, Hugging Face, Ollama, or LM Studio adapters;
- arbitrary OAuth providers;
- connector marketplace;
- Stripe checkout and paid subscriptions;
- enterprise administration;
- Alidora authoring or execution;
- CordiaAIE courses or certification;
- autonomous write actions;
- generalized workflow automation;
- full visual customization.

Alidora remains Cordia's advanced agentic-system studio over the same canonical
workspace contracts. CordiaAIE remains a separate certification and education
product. Neither owns MVP workspace state.

## 9. Framework completion gate

The framework is complete only when all of the following are true:

- the six contracts above exist in the real application path;
- one canonical workspace owns all runtime state;
- unsupported operations fail explicitly;
- no mock, placeholder, or catalog record reports live capability;
- deterministic local integration tests traverse the complete kernel and are
  labeled simulated;
- real-provider verification traverses the authenticated production route and
  records only bounded evidence;
- real-connector verification uses an approved credential at the adapter
  boundary and produces a visible artifact result;
- refresh, retry, duplicate submission, failure, sign-out, and resume behavior
  preserve canonical truth;
- the production bundle is reproducible from committed source; and
- the same saved workspace opens in the packaged Windows application.

## 10. Build sequence

### Sprint 1: Framework and real model

Finish the structural Task 4C corrections, consolidate the six contracts over
existing code, configure OpenAI, implement the ten-turn allowance, and observe
one authenticated real-provider turn.

### Sprint 2: Universal connector

Complete API-key/test-request, OpenAPI-import, and remote-MCP setup contracts.
Verify one real non-GitHub connector end to end. Keep OAuth-specific services
explicitly unavailable until supported.

### Sprint 3: Artifact and skill

Create one agent-proposed artifact and one generated read skill, require the
correct approval, execute one real connector operation, and visibly update the
artifact without leaking credentials or raw provider data.

### Sprint 4: Delivery

Run the complete human journey, package the Windows installer, verify the same
workspace after installation, deploy the reviewed commit, and repeat the public
journey against production.

## 11. Evidence language

Every report uses one of these labels:

- **Implemented:** source exists and focused tests pass.
- **Simulated:** the real application path was exercised with a deterministic
  provider or connector double.
- **Verified locally:** an approved real dependency was observed through the
  local authenticated application path.
- **Verified live:** the deployed public application was observed at a named
  commit through the complete relevant journey.
- **Not yet verified:** required real evidence does not exist.

Cordia is a functional beta only after the complete product outcome in Section
2 is verified live and through the packaged Windows application.
