# Cordia Operator Profile Decision Bridge

## Outcome

Make the Surveyor assessment an authenticated, non-scored operator profile that explains what Cordia understands, what evidence supports it, what Cordia is still learning, and the correct next action: refine, build, or open the latest saved workspace.

## Authority and ownership

- Surveyor profile storage remains owned by `surveyor.pipeline` and `surveyor.store`.
- Connector truth remains owned by the connector catalog and stored connector states.
- Saved interfaces and canonical workspace state remain the only workspace owners.
- The new endpoint is a read-only projection. It creates no profile, workspace, approval, connector, or scoring state.
- Surveyor remains the only refinement path. Existing safe workspace navigation remains the only dashboard-link builder.

## Safe projection contract

The browser may receive only:

- bounded positive identifier display fields and descriptive evidence strength;
- bounded understanding and evidence snippets that reject credential- or local-path-shaped text;
- known connector names, explicit user state, and implementation status;
- one bounded learning/next-action record;
- at most one newest workspace reduced to safe identifier and display name.

The projection must not expose scores, criteria, numeric confidence/completeness, transcripts, intent misses, raw artifacts, connector catalogs, interface definitions, secrets, or local paths.

## Tasks and evidence gates

1. Add backend RED tests for the exact projection allow-list, owner scoping, learning states, safe text handling, and unauthenticated fail-closed behavior.
2. Implement the projection by composing existing profile, assessment, connector-state, and saved-interface reads.
3. Add frontend RED tests for safe Refine / Build / Open decisions, malformed recovery, private-field rejection, and fixed navigation.
4. Update `profile.html` to consume only the bounded projection, refresh after Surveyor updates, and show visible recovery instead of a blank section.
5. Route the account menu's Assessment entry to the Surveyor operator-profile section and relabel the legacy scored page as certification-specific.
6. Run focused and full backend/web regressions, syntax/diff checks, and an independent review before publishing.

## Explicitly out of scope

- Changing Surveyor inference or scoring algorithms.
- Creating a second assessment/profile store.
- Treating catalog presence as connector authorization.
- Editing, executing, approving, or deploying a workspace from the assessment endpoint.
- Claiming live-model semantic compliance or completing the wider desktop/Alidora roadmap.
