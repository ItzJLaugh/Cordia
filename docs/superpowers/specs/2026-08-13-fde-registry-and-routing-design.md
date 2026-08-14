# Cordia FDE Registry and Routing Design

## Goal

Give Cordia one inspectable source of truth for which skills, capabilities,
connector prerequisites, industry playbooks, and evidence requirements apply to
the user's current FDE mission. The registry improves agent choice without
creating a hidden scoring system, a second workspace model, or autonomous
self-modification.

## Reused contracts

- `library.py` remains the profile/framework recommendation source.
- Surveyor evidence and `operator.md`, `connectors.md`, `intent-misses.md`
  remain the source understanding.
- `fde-tasks.md` remains the concise workspace-specific mission brief.
- `skills.py`, `capability_gateway.py`, and `permissions.py` remain execution
  truth. A registry record never makes an unavailable capability executable.
- Canonical workspace state remains authoritative for connected systems and
  confirmed local contexts.

## Registry model

The initial registry is versioned Python manifest data, not a database table.
Each record has a stable ID, kind (`skill` or `playbook`), summary, tags,
required capabilities, required connectors, required evidence categories,
permission posture, expected safe result fields, maturity, and test evidence.

Playbooks are declarative industry/use-case bundles that reference existing
skill IDs. They may recommend a sequence or workspace surface, but cannot run
code, define an arbitrary tool call, or bypass the capability gateway.

The first seed entries are:

1. `local_git_status_wait` for developer/repository monitoring.
2. `local_git_pull` and `local_git_push` with approval-required posture.
3. `github_repository_review` for cloud repository context.
4. `developer_delivery_loop` playbook combining the above where prerequisites
   are met.

## Agent routing

Routing proceeds in deterministic stages:

1. Filter: reject records whose capability is absent, connector/local context
   is unconfirmed, permission is DENY, or required evidence is unavailable.
2. Score remaining records using visible terms:

```text
score = mission_relevance
      + evidence_support
      + explicit_preference
      + observed_success
      - risk_cost
      - latency_cost
```

Every term is a small bounded integer with an explanation. `observed_success`
is initially zero; the registry does not infer success from unverified claims.
Tie-break by stable record ID. A selected/recommended result includes `why`,
matched evidence IDs/categories, blocked prerequisites, permission decision,
and the score breakdown. No overall user score or hidden ranking is produced.

## Speed and reasoning policy

- Static manifests are loaded once and copied on read.
- Filtering/ranking is rule-based and local; no model call is needed for a
  clear capability request.
- The runtime asks a deeper planner only when there are multiple near-tied
  candidates, conflicting intent evidence, or a multi-step plan needing human
  explanation. It receives only registry-safe summaries and artifact excerpts,
  never connector secrets or local paths.
- Routing has a fixed candidate limit and returns an explicit fallback when no
  record qualifies; it does not search indefinitely.
- Personalization modes remain respected: `off` ignores profile evidence,
  `simple` uses explicit evidence and rules, `adaptive` remains a safe
  compatibility layer rather than an opaque optimizer.

## Learning loop

Intent misses and recorded skill outcomes produce inspectable events. A human
can confirm a result as useful or not useful. The first slice records outcomes
but does not automatically change routing weights. A later reviewed policy may
promote repeated, attributable outcomes into bounded per-record adjustments.
Every adjustment must identify the evidence/events that caused it and can be
disabled globally.

## Safety

- Registry is advisory; gateway and permission checks remain mandatory at
  execution time.
- `ASK` is never converted to `ALLOW` by a high routing score.
- Unknown record/capability/skill IDs are rejected.
- Records cannot define shell strings, raw connector requests, secrets,
  filesystem paths, or unbounded agent prompts.
- The agent receives safe result schemas and reasoning traces, not raw
  connector/local machine internals.

## Verification

1. Test registry schema validation and stable IDs.
2. Test filtering for absent connector/local context, missing evidence, and
   DENY permission.
3. Test ranking explainability, deterministic ties, latency/risk penalties,
   personalization-off behavior, and candidate limits.
4. Test playbooks cannot introduce unregistered skills/capabilities.
5. Test recommendations do not make a blocked skill executable.
6. Test intent-miss/outcome records remain inspectable and do not auto-adjust
   routing in the initial slice.

## Non-goals

- A broad connector database or marketplace.
- Vector search, embeddings, opaque learning models, or self-modifying agent
  prompts.
- Executing a skill directly from a registry recommendation.
- Replacing Surveyor artifacts, canonical workspace state, or existing
  permissions/capability manifests.
