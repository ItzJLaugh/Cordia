# Cordia FDE Registry and Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task.

**Goal:** Add an inspectable FDE skill/playbook registry and deterministic recommendation engine that reuses Cordia's existing artifacts, skills, capability gateway, permissions, and intent-miss contracts.

**Architecture:** `fde_registry.py` holds immutable declarative records; `fde_routing.py` validates context, filters unavailable records, ranks safe candidates with visible bounded terms, and returns a reason trace. The registry is advisory only: runtime execution continues through `skills.py`, `capability_gateway.py`, and `permissions.py`.

**Tech Stack:** Python standard library, current Surveyor test harness, existing skill/capability/permission manifests.

**Spec:** `docs/superpowers/specs/2026-08-13-fde-registry-and-routing-design.md`

## Global Constraints

- Reuse existing contracts; do not create a duplicate skill/capability or workspace state system.
- Registry records are static copied manifests with stable IDs, schema validation, and no executable code, shell commands, raw requests, secrets, paths, or prompts.
- Routing is deterministic, bounded, and explainable; ties use stable IDs.
- Permission/gateway truth remains mandatory; `ASK` never becomes `ALLOW` due to ranking.
- `off` mode ignores profile evidence; no automatic learning/weight adjustment in this slice.

### Task 1: Add static registry schema and seed records

**Files:** Create `backend/surveyor/fde_registry.py`, `backend/tests/test_fde_registry.py`; modify `backend/surveyor/__init__.py`.

- [ ] Write red tests for copied catalog returns, duplicate/unknown IDs, schema rejection, record-safe fields, known skill references, and the four seed records.
- [ ] Run `cd backend && python -m unittest tests.test_fde_registry -v` and confirm red.
- [ ] Implement `catalog()`, `describe(id)`, `validate(record)`, static skill/playbook records, and validation that required skills/capabilities exist in existing registries.
- [ ] Re-run focused tests green.

### Task 2: Add deterministic FDE routing

**Files:** Create `backend/surveyor/fde_routing.py`, `backend/tests/test_fde_routing.py`.

- [ ] Write red tests for unavailable connector/local context, missing evidence, DENY filtering, candidate limit, deterministic tie order, risk/latency penalties, off-mode evidence suppression, and score-breakdown reason trace.
- [ ] Run `cd backend && python -m unittest tests.test_fde_routing -v` and confirm red.
- [ ] Implement `recommend(context, limit=5)` using explicit bounded relevance, evidence, preference, success, risk, and latency terms; return `recommendations`, `blocked`, and safe explanations only.
- [ ] Re-run focused tests green.

### Task 3: Integrate registry with safe runtime views

**Files:** Modify `backend/surveyor/skills.py`, `backend/training_backend.py`, `backend/tests/test_skills.py`; create `backend/tests/test_fde_registry_endpoint.py`.

- [ ] Write red tests proving registry recommendations cannot execute blocked skills, and an authenticated endpoint returns safe recommendations/blocked prerequisites without secrets or local paths.
- [ ] Run focused backend tests and confirm red.
- [ ] Add `GET /surveyor/fde-recommendations`, compose existing connector/local states and artifact evidence into routing context, and expose recommendation trace separately from execute endpoints.
- [ ] Re-run focused tests green.

### Task 4: Record inspectable outcomes and verify full slice

**Files:** Modify `backend/surveyor/intent_misses.py`, `backend/surveyor/store.py`, `backend/tests/test_intent_misses.py`, `backend/tests/test_fde_routing.py`, `backend/surveyor/README.md`.

- [ ] Write red tests for useful/not-useful outcome events that retain record ID and do not alter current routing weights automatically.
- [ ] Run focused tests and confirm red.
- [ ] Add bounded event recording, safe README guidance, and explicit no-auto-adjust behavior.
- [ ] Run `cd backend && python -m unittest discover -s tests -v`, `cd desktop && npm.cmd test`, `node --check desktop/main.js`, and `git diff --check`; confirm green.
