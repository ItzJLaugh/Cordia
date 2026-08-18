# Workspace Inspection Dock Implementation Plan

**Goal:** Add Cordia's documented bottom inspection dock to the primary Workspace view using the existing renderer-safe canonical projection.

## Contract

- Render exactly six fixed tabs in this order: Connected, Skills, Access, Context, Automations, Activity.
- Derive every row from the already-sanitized `workspaceRendererModel`; do not add endpoints, stores, connector reads, or execution paths.
- Keep the dock read-only. Skill execution remains on the existing artifact card and is not duplicated in the dock.
- Treat Access as Cordia capability policy, not human RBAC. Never expose policy reasons.
- Treat Activity as recent account activity, not workspace-scoped history. Never expose event payloads.
- Show `No automations configured` only when canonical `workspace.automations` is an empty array. Unknown or non-empty automation shapes fail closed as `Automation details are unavailable` until a typed automation contract exists.
- Do not render the dock in Alidora.
- Preserve the existing card model and canonical workspace owner.

## Tasks

1. Add RED model tests for tab order, safe category mapping, empty states, malformed automations, and sensitive-field exclusion.
2. Add RED component tests for accessible tab behavior, a single visible panel, truthful empty/error copy, and no action controls.
3. Implement the bounded dock model and `InspectionDock` component.
4. Place the dock below the primary DashView and add responsive styling without changing Alidora.
5. Update only the directly proven Phase 5 and Phase 9 checklist items.
6. Run the dashboard suite, production build, packaged-output provenance checks, diff checks, and an independent review before publishing.

## Verification boundary

This slice proves an inspectable UI projection only. It does not prove automation execution, LiveView, window move/resize, builder/runtime identity, human-role permissions, or immediate mutation propagation.
