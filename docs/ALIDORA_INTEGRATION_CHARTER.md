# Alidora Integration Charter

## Product definition

**Alidora — Agentic System Builder by Cordia** makes it understandable and practical to build, inspect, and operate a company agentic system behind a Cordia workspace.

Cordia remains the conversational Forward Deployed Engineer and everyday operating environment. Alidora is its advanced system-building module.

## Foundation status (in review)

The current branch packages an authenticated, read-only Alidora System Map and links it from the non-primary Cordia workspace navigation without changing Cordia's chat-first default. The visible foundation is limited to safe agent/skill topology plus catalog-backed connectors with explicit consent, implementation, lifecycle, and runtime status. It remains in review until an independent re-review passes.

Permissions, provenance, artifact purpose/source/view-mode/action inspection, authoring, execution, connector setup, LiveView, approval decisions, runs, and traces remain deferred. The map has no independent state, execution, connector, or approval path.

## User-facing role

Cordia's default surface is the FDE Workspace: Surveyor-informed, chat-first, connector-native, and task-oriented.

Alidora is a named tab/module for users who need to:

- inspect a workspace as agents, stages, skills, connectors, and dependencies;
- compose or refine advanced multi-agent workflows;
- see runs, traces, checkpoints, and system health;
- create reusable company agentic systems.

The product must not force a new user into a graph editor before Cordia has understood their work.

The complete Alidora product is intended to explain the system behind agent-built workspace artifacts: why a DashView exists, the connectors/skills/artifacts it depends on, provenance, exposed actions, and whether an optional LiveView has been explicitly enabled. This foundation does not render those artifact or view-mode details.

## Shared foundation and non-negotiable boundaries

Alidora consumes and acts through Cordia-owned contracts:

| Concern | Single owner | Alidora role |
| --- | --- | --- |
| Operator/profile/evidence and artifacts | Surveyor + artifact compiler | Read and explain |
| Workspace state and provenance | Canonical workspace state | Project and mutate through typed state operations |
| Connectors, tools, scripts, and skills | Cordia capability registry/gateway | Select/configure; never duplicate catalogs |
| Permissions, approvals, audit | Cordia ALLOW / ASK / DENY runtime | Display and request; never bypass |
| Secrets | Cordia vault/secret references | Consume neither vault values nor raw-secret fields |
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
- the foundation map structurally omits arbitrary workspace titles/descriptions and entity names/descriptions, context values, mutations, provenance, and artifact text;
- the only canonical locator returned is a grammar-bounded workspace id; agent/skill display identities are synthetic, while connector labels and all connector status values come from catalog constants and validated enums. This boundary does not claim to classify every arbitrary secret-shaped identifier;
- source tests and relevant frontend build pass in the correct runtime directory;
- the Cordia Workspace and Alidora show the same post-mutation canonical state.

Reproduce the dashboard dependency tree and production bundle on Node `^20.19.0 || >=22.12.0` from the repository root:

```powershell
Set-Location dashboard-app
npm.cmd ci
npm.cmd test
npm.cmd run build
```

The build must leave `web/dashboard/index.html` and every referenced hashed asset staged or committed together.

## Merge policy

Sophistication is evidence, not permission to blindly merge. Prefer the implementation with the better verified contract, safety behavior, integration cost, and product leverage. Compose complementary components; replace overlapping ownership systems deliberately.
