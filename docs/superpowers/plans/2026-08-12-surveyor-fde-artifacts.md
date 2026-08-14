# Surveyor FDE Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist inspectable Surveyor source artifacts and compile them into safe FDE runtime artifacts.

**Architecture:** A pure Surveyor-adjacent compiler produces Markdown from the existing profile contract and connector confirmations. The existing Postgres store persists the bundle and the existing backend exposes it without changing the old interface compiler or builder.

**Tech Stack:** Python standard library, existing PostgreSQL store, Python `unittest`.

**Spec:** `docs/superpowers/specs/2026-08-12-surveyor-fde-artifacts-design.md`

## Global Constraints

- Preserve Surveyor's conversational flow and existing profile contract.
- Keep source artifacts separate from compiled runtime artifacts.
- Never infer connector authorization; mark unconfirmed connectors as suggested.
- Default consequential actions to ASK or DENY.
- Do not create a parallel workspace or interface-definition compiler.

---

### Task 1: Pure Artifact Compiler

**Files:**
- Create: `backend/surveyor/artifacts.py`
- Test: `backend/tests/test_artifacts.py`

**Interfaces:**
- Consumes: `compile_artifacts(profile: dict, confirmed_connector_ids: list[str] | None = None) -> dict`
- Produces: a six-document bundle keyed by the canonical artifact filenames.

- [x] **Step 1: Write failing tests** for evidence-backed operator output, confirmed versus suggested connector output, runtime separation, and safe permissions.
- [x] **Step 2: Run** `python -m unittest tests.test_artifacts -v` and verify failure because `surveyor.artifacts` is absent.
- [x] **Step 3: Implement** the smallest deterministic artifact compiler and provider-neutral catalog.
- [x] **Step 4: Run** `python -m unittest tests.test_artifacts -v` and verify success.

### Task 2: Persistence and Existing Surveyor API

**Files:**
- Modify: `backend/surveyor/store.py`
- Modify: `backend/training_backend.py`
- Test: `backend/tests/test_artifacts.py`

**Interfaces:**
- Consumes: `store.save_artifacts(email, bundle)` and `store.get_artifacts(email)`.
- Produces: authenticated `GET /surveyor/artifacts` output, generated on demand from the saved Surveyor profile.

- [x] **Step 1: Write failing tests** for the API-facing bundle composition helper if it is extracted.
- [x] **Step 2: Run** the targeted test and verify failure.
- [x] **Step 3: Add** the smallest store schema/table and authenticated route without altering conversation behavior.
- [x] **Step 4: Run** targeted and full backend unit tests.
