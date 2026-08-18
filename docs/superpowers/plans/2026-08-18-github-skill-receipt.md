# GitHub Skill Receipt and DashView Refresh

## Outcome

Close Cordia's first real-work loop: one click on the existing Review GitHub
repositories skill executes the existing authenticated ALLOW capability, adds a
bounded evidence-backed receipt to Cordia chat, and refreshes the canonical
workspace so the existing GitHub DashView reflects current repository data.

## Existing authority

- `surveyor.skills` remains the skill registry and declaration owner.
- `capability_gateway` and `permissions` remain the only execution gate.
- `_github_read_capability` remains the only secret-resolution and GitHub read boundary.
- The canonical workspace refresh and existing GitHub DashView remain the visual result path.
- The skill response adds no repository cache, transcript store, connector state, or execution path.

## Safe receipt contract

The skill execution response may expose only:

- `ok: true`;
- the exact executed `skill_id`;
- `result.repository_count`, an integer from 0 through 30.

Repository names, descriptions, URLs, branches, provider errors, secret references,
tokens, local paths, capability internals, and permission internals must not enter
the chat receipt. Repository details remain confined to the existing bounded
GitHub DashView projection after canonical refresh.

## TDD tasks

1. Add handler-level RED tests for authenticated, confirmed GitHub ALLOW execution,
   exact safe receipt output, bounded provider rows, audit count, and unconfirmed
   fail-closed behavior before secret resolution.
2. Add dashboard RED tests for exact skill/result binding, singular/plural count
   copy, generic-success fallback for malformed or injected results, and exactly
   one canonical refresh.
3. Implement the smallest response projection and receipt parser without changing
   the existing registry, permission gate, vault, connector, or refresh coordinator.
4. Rebuild the committed dashboard release, run the full regression matrix, and
   obtain independent review before publication.

## Explicitly out of scope

- Natural-language planning or autonomous skill selection.
- A second GitHub adapter, connector, cache, or result store.
- ASK continuation, write operations, or additional connectors.
- Rendering repository details in chat.
- Claiming the change is live before Hostinger deployment and public verification.
