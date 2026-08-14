# Alidora Integration Charter

## Product definition

**Alidora — Agentic System Builder by Cordia** makes it understandable and practical to build, inspect, and operate a company agentic system behind a Cordia workspace.

Cordia remains the conversational Forward Deployed Engineer and everyday operating environment. Alidora is its advanced system-building module.

## User-facing role

Cordia's default surface is the FDE Workspace: Surveyor-informed, chat-first, connector-native, and task-oriented.

Alidora is a named tab/module for users who need to:

- inspect a workspace as agents, stages, skills, connectors, and dependencies;
- compose or refine advanced multi-agent workflows;
- see runs, traces, checkpoints, and system health;
- create reusable company agentic systems.

The product must not force a new user into a graph editor before Cordia has understood their work.

Alidora explains the system behind agent-built workspace artifacts: why a DashView exists, the connectors/skills/artifacts it depends on, provenance, exposed actions, and whether an optional LiveView has been explicitly enabled.

## Shared foundation and non-negotiable boundaries

Alidora consumes and acts through Cordia-owned contracts:

| Concern | Single owner | Alidora role |
| --- | --- | --- |
| Operator/profile/evidence and artifacts | Surveyor + artifact compiler | Read and explain |
| Workspace state and provenance | Canonical workspace state | Project and mutate through typed state operations |
| Connectors, tools, scripts, and skills | Cordia capability registry/gateway | Select/configure; never duplicate catalogs |
| Permissions, approvals, audit | Cordia ALLOW / ASK / DENY runtime | Display and request; never bypass |
| Secrets | Cordia vault/secret references | Never read or expose |
| Outcomes and intent misses | Cordia bounded feedback pipeline | Link to, never replace |

No Alidora feature may create an alternate execution gateway, hidden graph state, independent connector truth, independent permission decision, raw-secret path, or competing self-learning loop.

## Integration sequence

1. **Merge review:** assess parallel work component by component with verification evidence and classify it adopt/adapt/compose/reject.
2. **Contract alignment:** map graph/interface definitions to canonical workspace state, registry manifests, permissions, provenance, and safe result types.
3. **Read-only system map:** render canonical state as an Alidora graph with no new state authority.
4. **Inspectable operations:** add safe run status, traces, and approval checkpoints through existing audit/capability boundaries.
5. **Guarded authoring:** allow typed changes only through canonical state mutations and Cordia approvals.
6. **Reusable company systems:** package verified workflows as templates/playbooks only after shared contracts and operational safety are proven.

## Verification bar

Before accepting any Alidora component, verify:

- state/provenance ownership is singular and explicit;
- capabilities have confirmed connector/runtime prerequisites;
- ASK and DENY cannot be bypassed by UI or direct handler calls;
- renderer/API output excludes secrets, raw credentials, and local paths;
- source tests and relevant frontend build pass in the correct runtime directory;
- the Cordia Workspace and Alidora show the same post-mutation canonical state.

## Merge policy

Sophistication is evidence, not permission to blindly merge. Prefer the implementation with the better verified contract, safety behavior, integration cost, and product leverage. Compose complementary components; replace overlapping ownership systems deliberately.
