# Surveyor FDE Artifacts Design

## Scope

Build the first usable bridge from Surveyor understanding to inspectable, persisted FDE runtime context. This slice does not replace the existing interface-definition compiler or manual builder.

## Existing Contracts

- `surveyor.pipeline` already owns the conversational turn and structured profile lifecycle.
- `surveyor.store` already persists profiles, transcript messages, and interface definitions under the authenticated email.
- `surveyor.cordia_compiler_adapter` is an unimplemented future compiler for old interface definitions; it remains untouched.
- `web/builder.html` remains a manual editor until a later canonical-workspace-state slice.

## Design

Add a pure `surveyor.artifacts` compiler that consumes a Surveyor profile and explicit connector confirmations. It emits separate source documents (`operator.md`, `connectors.md`, `intent-misses.md`) and derived runtime documents (`fde-tasks.md`, `permissions.md`, `workspace-plan.md`). Each source document carries evidence snippets or confirmation status; runtime documents summarize operational guidance without copying the transcript.

Persist the generated document bundle per email through the existing Surveyor store, and expose it from the existing Surveyor backend. The compiler is deterministic, inspectable, and does not call an LLM.

## Connector Compatibility Contract

Connector records are provider-neutral manifests with an id, display name, capability tags, setup modes, runtime transports, and explicit confirmation status. Supported transports are direct API, MCP, and local bridge; supported setup modes are OAuth, API key, MCP connection, and guided browser setup. Browser setup is a fallback, not durable runtime.

The initial catalog names common productivity, development, messaging, storage, automation, and web connectors commonly offered in ChatGPT and Anthropic ecosystems. Catalog presence means Cordia can represent and plan the connector. It does not grant credentials, assert vendor availability, or imply a completed adapter.

## Permissions

The compiler maps inferred delegation and risk preferences to plain `ALLOW`, `ASK`, and `DENY` guidance. It defaults consequential external actions to `ASK`; it never grants sending, publishing, deletion, credential access, or payment authority from profile inference alone.

## Tests

Stdlib `unittest` tests prove that generated artifacts preserve evidence, distinguish confirmed from suggested connectors, keep source and runtime artifacts separate, produce concise mission guidance, and use safe default permissions.
