# Cordia Task 4C Structural Truth Design

**Status:** Proposed for implementation
**Parent:** `2026-08-20-cordia-thin-spine-design.md` and Task 4 of the thin-spine plan
**Purpose:** Remove semantic regex policing from the Cordia Agent's operational truth boundary.

## Problem

Task 4 correctly limits the provider to five envelope kinds, but it still lets the
provider write user-visible `speech` for every kind. The backend then tries to
decide whether arbitrary prose falsely claims that Cordia connected, configured,
ran, approved, or completed work. Repeated review proved that phrase-level regex
cannot reliably distinguish affirmative claims, questions, negation,
counterfactuals, coordinated clauses, and ordinary relational language.

The small-core boundary must not depend on understanding arbitrary prose.
Operational truth must come from deterministic state and deterministic copy.

## Approaches Considered

### 1. Continue expanding semantic regexes

Rejected. It is small in line count but unbounded in behavior, overblocks normal
language, and keeps producing new bypasses.

### 2. Add a second model as a truth verifier

Rejected. It increases cost and latency, can disagree with the first model, and
still does not provide a deterministic security boundary.

### 3. Deterministic action copy plus narrow conversational speech

Selected. Provider prose is never used to describe the outcome of an action.
Action envelopes contain only structured proposal data. Cordia renders fixed
copy from the validated kind and deterministic action state. Free-form `speak`
remains available for ordinary conversation, but a compact token gate redirects
operational-status language to a fixed clarification instead of attempting to
interpret its meaning.

## Agent Envelope Contract

The five kinds remain unchanged:

1. `speak`
2. `propose_connector`
3. `create_artifact`
4. `propose_skill`
5. `run_approved_skill`

### Speak

```json
{
  "kind": "speak",
  "speech": "ordinary conversational text"
}
```

`speech` is bounded and privacy-screened. A normalized token scan rejects the
operational vocabulary families `connect`, `configure`, `setup`, `run`,
`execute`, `deploy`, `create`, `approve`, `complete`, `live`, `enabled`,
`active`, `ready`, and `available`. This scan is intentionally conservative and
does not try to infer polarity, grammar, or truth.

When the provider uses operational vocabulary in `speak`, Cordia does not return
502 and does not expose that prose. It returns fixed deterministic copy:

> I can discuss that, but workspace status and changes must use a Cordia action.

This is a safe recovery, not a successful action and not a model claim.

### Action envelopes

Action envelopes no longer accept provider-controlled `speech`:

```json
{
  "kind": "propose_connector",
  "proposal": { "...": "validated fields only" }
}
```

The same applies to `create_artifact`, `propose_skill`, and
`run_approved_skill`. Unknown fields, including `speech`, are rejected.

After deterministic processing, the server adds user-visible copy to the public
response from fixed templates:

- `propose_connector`: `I prepared a connector setup card.`
- `create_artifact`: `I prepared a proposed workspace artifact.`
- `propose_skill`: `I prepared a proposed skill for review.`
- `run_approved_skill` before execution: `This skill requires approval before it can run.`

Public copy contains no provider-controlled connector field. Display names remain
structured proposal/card data only. Templates never state that a connector is
available, an artifact is committed, or a skill ran unless deterministic runtime
state proves that outcome. Task 4 still executes nothing.

## Data Flow

1. The provider returns one exact envelope.
2. Backend validation enforces the exact kind-specific schema and privacy rules.
3. `speak` either returns safe conversational text or the fixed operational
   clarification.
4. An action envelope is applied to canonical pending state exactly once.
5. The backend creates fixed public copy from the resulting deterministic state.
6. The dashboard renders the server copy and canonical workspace revision.

Provider prose is never persisted as the outcome text for an action envelope.

## Connector Runtime Truth on Creation

Every workspace creation/materialization path must call the same locked
`_workspace_from_current_connectors` projection with runtime reconciliation
enabled. No path may pass `include_runtime=False`. The owner workspace-set lock
is acquired before connector state/runtime is read and held through insertion.
The created workspace therefore inherits the latest canonical connector and
runtime truth while preserving its non-connector fields.

## Revision-Conflict Recovery

A `409 revision_conflict` is an ambiguous retry state, not a terminal validation
failure:

1. Keep the draft text and its existing idempotency key.
2. Refresh the canonical workspace once.
3. Replace the local revision with the refreshed revision.
4. Show fixed recovery copy asking the user to retry.
5. The next send reuses the same idempotency key.

The dashboard does not automatically call the model twice. Definitive malformed
request responses may clear retry identity; transport failures, malformed
successful responses, provider 5xx responses, and revision conflicts retain it.

## Persistence and Safety

- Existing compare-and-save, owner scoping, tagged history, and transactional
  derived projections remain unchanged.
- Action proposal persistence remains exact-once by owner, workspace, and
  idempotency key.
- No connector or skill executes in Task 4C.
- No real-provider evidence is claimed without an approved credential and an
  actual authenticated production-route observation.
- CordiaAIE and Alidora remain outside this correction.

## Testing

### Contract tests

- Every action kind rejects provider `speech` and unknown fields.
- Deterministic public copy matches the validated action/result state.
- Operational `speak` variants with affirmative, negative, conditional,
  coordinated, or punctuated grammar all produce the same fixed clarification;
  ordinary non-operational conversation is preserved.
- No provider action prose enters runs, events, pending actions, or API output.

### Persistence tests

- All creation/materialization paths inherit latest connector runtime truth.
- A stale pre-lock candidate cannot restore old connector state.
- Existing owner, idempotency, compare-and-save, and rollback tests remain green.

### Dashboard tests

- A revision conflict performs exactly one canonical refresh.
- Draft and idempotency key survive the conflict.
- Retry uses the same key and refreshed revision.
- No automatic duplicate provider request occurs.

### Verification boundary

Focused and full local suites prove the deterministic contract. They do not prove
a live provider. A real-provider result remains **Not yet verified** until the
approved production evidence gate is run.

## Scope Exclusions

- Universal connector execution (Task 5)
- Artifact execution and generated skill execution (Tasks 6-7)
- OAuth providers
- Billing, desktop packaging, Alidora execution, and CordiaAIE
