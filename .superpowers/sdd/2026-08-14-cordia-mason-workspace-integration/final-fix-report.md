# Final whole-branch fix report

Reviewed base: `38e36d607fc7f6457578519c83d98825f883bb24`

Implementation commit: `724fad639f2fc9adf9a69d277883d25d6ca1446b` (`fix(dashboard): close final workspace review findings`)

## Scope completed

- Centralized the renderer identifier and sensitive-text contracts. Canonical workspace fields now reject credential prefixes and drive-relative/absolute paths consistently; Alidora accepts only bounded typed synthetic entity ids.
- Projected an inline current-run approval only as `approvalStatus: "pending"` and fixed pause copy. No checkpoint id, run id, step id, summary, payload, or account-wide approval feed reaches renderer state.
- Kept capability policy authoritative with `Allowed by policy`, `Approval required`, and `Not allowed` badges while rendering connector readiness as a separate bounded row.
- Restored the canonical `github-repositories` window as a bounded artifact with a single fixed same-origin `/github.html` link and available, setup-required, unavailable, and needs-attention states.
- Added bounded rate-limited/partial supplemental-feed status, corrected failed-refresh copy to require reload, and labeled the unscoped activity feed `Recent account activity`.
- Removed the plan file's trailing blank line.

## Focused TDD evidence

All focused commands ran from `dashboard-app`.

1. Renderer privacy matrix

   - RED: `node --test test/workspace.test.js test/workspace-view.test.js src/graph.test.js` — 27 passed, 4 failed for admitted `sk-`/AKIA values, unsafe agent text, and untyped Alidora ids.
   - GREEN: same command — 31 passed, 0 failed.

2. Current-run pending approval

   - RED: `node --test --test-name-pattern="current-run pending approval" test/workspace-view.test.js` — 0 passed, 1 failed because no safe status or pause copy was projected.
   - GREEN: same command — 1 passed, 0 failed.

3. Capability policy and readiness matrix

   - RED: `node --test --test-name-pattern="capability|readiness" test/workspace-view.test.js` — 0 passed, 2 failed because connector state replaced policy badges.
   - GREEN: same command — 2 passed, 0 failed.

4. GitHub repository surface

   - RED: `node --test --test-name-pattern="GitHub repository artifact|declared GitHub|fixed same-origin" test/workspace-view.test.js test/artifact-card.test.js` — 0 passed, 3 failed after the render harness was corrected to fail cleanly on the missing fixed-link control.
   - GREEN: same command — 3 passed, 0 failed.

5. Supplemental-feed completeness status

   - RED: `node --test --test-name-pattern="bounded rate-limited" test/workspace-view.test.js` — 0 passed, 1 failed because no bounded feed status existed.
   - GREEN: same command — 1 passed, 0 failed.

6. Failed post-skill refresh copy

   - RED: `node --test --test-name-pattern="failed canonical refresh|failed post-skill refresh" test/skill-interaction.test.js` — 0 passed, 2 failed because stale in-progress or empty copy remained.
   - GREEN: same command — 2 passed, 0 failed.

7. Account-wide activity label

   - RED: `node --test --test-name-pattern="labels the unscoped feed" test/workspace-view.test.js` — 0 passed, 1 failed with `Recent activity`.
   - GREEN: same command — 1 passed, 0 failed with `Recent account activity`.

## Full verification

- Dashboard: `npm.cmd test` in `dashboard-app` — 49 passed, 0 failed.
- Desktop: `npm.cmd test` in `desktop` — 46 passed, 0 failed. The pre-commit run intentionally failed only the HEAD-byte guard; the committed rerun passed all provenance tests.
- Backend: `py -3.13 -m unittest discover -s tests -v` in `backend` — 143 passed, 0 failed in 6.349 seconds. Existing optional `sentence_transformers`, NumPy reload, and unreachable test-database notices remained non-failing.
- Production build: `npm.cmd run build` in `dashboard-app` — Vite 7.3.6 transformed 200 modules and completed in 2.04 seconds. The sandbox-blocked attempt was rerun through the approved build-command escalation.
- Syntax: `node --check` passed for `api.js`, `ArtifactLink.js`, `graph.js`, `identifier.js`, `SkillAction.js`, `workspace-view.js`, `workspace.js`, and all changed standalone test files.
- Diff hygiene: `git diff --check`, `git diff --check origin/main`, and `git diff --cached --check` passed; the plan EOF warning is gone.
- Backend surface scan: `rg -n -F "/dashboard/" backend` returned no matches.
- Fixed-route scan: renderer source contains only the bounded Surveyor reads plus fixed `/surveyor/run`, `/surveyor/skill/execute`, and `/surveyor/alidora/map` routes; no approvals/decision route was found.
- Generic execution scan: no new child-process, spawn, shell, or exec surface was found in the scoped renderer sources.
- Credential scan: no high-entropy `sk-`, GitHub PAT, AWS access-key, or Slack token literal was found in committed `web/dashboard` JavaScript.
- Privacy scan: no local user path or private approval/refresh fixture literal was found in committed `web/dashboard` JavaScript.

## Committed production assets and provenance

Clean-HEAD verifier command: `npm.cmd run verify:dashboard-release` in `desktop`.

Result: clean `npm ci` installed 137 packages, Vite transformed 200 modules, and every rebuilt byte matched commit `724fad639f2fc9adf9a69d277883d25d6ca1446b`.

- Source SHA-256: `cbe80c192960a29c75fb7db28db716d3f0ee5991902cb48a69760b150bd5776f`
- `web/dashboard/assets/index-CP-PMxsD.css`: `b76415d479b5681dcd5af16712535dca375c36ad50b2f03f735fbcc9e2bdff61`
- `web/dashboard/assets/index-sRAzhEY1.js`: `9f814115eb3b009e6935f906c88f92e97f2ec06886e5078754520dbb20fd2822`
- `web/dashboard/build-provenance.json`: `b035cdadbdcd1085f74d3d0eb4d72964f9973bfd33e0e7668c9545e8c14a5a3b`
- `web/dashboard/index.html`: `bce714f71ab178c914b41c80d4ebc03ac6e228574995ce913ed27014466227f9`

## Self-review

- The final diff stays inside the approved renderer/tests/build output/plan/report scope; no Mason backend, store, registry, execution, or outcome system was added.
- Cordia remains the chat-first owner of canonical state, auth, connectors, capabilities, permissions, approvals, execution, secrets, and outcomes. Alidora remains read-only.
- The GitHub artifact constructs one fixed same-origin link and never copies a connector result, response object, arbitrary URL, query token, method, command, or credential.
- ASK and DENY remain authoritative independently of connector readiness; the server gate and skill execution contracts are unchanged.
- Current-run approval handling does not render or store checkpoint details and does not imply that a protected continuation occurred.
- Partial/rate-limited feed state is derived only from the four fixed supplemental endpoints and exposes only allow-listed labels.
- No unresolved Critical, Important, or listed minor finding remains in the final-fix brief.
