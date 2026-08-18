# GitHub Secret Runtime Proof Plan

**Goal:** Prove the existing GitHub token lifecycle end to end without expanding connector scope or creating a new execution path.

## Contract

- Use the existing authenticated GitHub setup and skill-execution routes.
- Validate the raw token only at the provider-validation boundary.
- Persist only encrypted ciphertext and an opaque secret reference.
- Refuse execution before secret resolution when GitHub is unconfirmed or not ALLOW.
- Resolve plaintext only inside the allowed capability execution closure and pass it only to the existing GitHub adapter.
- Return only the existing bounded repository count receipt.
- Never place plaintext, ciphertext, provider rows, credential-shaped data, local paths, or raw provider errors in responses or audit events.
- Do not call an LLM, add a connector, add a skill, add approval continuation, or add another vault/state owner.

## TDD tasks

1. Add a route-level RED test that runs setup and skill execution for one authenticated owner using a sentinel token.
2. Assert validation, encryption/storage, permission ordering, adapter-boundary resolution, bounded response, and safe audit records.
3. Patch only an exposed boundary defect; otherwise retain production code unchanged and treat the integration proof as the deliverable.
4. Update README/TODO only for behavior directly proven by the test.
5. Run focused and full backend tests, diff checks, and independent review before committing.

## Explicitly deferred

GitHub writes, ASK continuation, browser-assisted setup, arbitrary token-bearing network restrictions, and broad claims that no raw secret can ever enter every future prompt remain open.
