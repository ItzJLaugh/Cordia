#!/usr/bin/env python3
"""Skills library and deterministic retrieval for the dashboard builder.

A *skill* is something the builder can wire into an interface: a reusable
capability (``kind: skill``), an external connection (``connector``), or an
MCP server (``mcp``). The library is an in-code catalogue, the same pattern
as ``adaptation._AGENTS`` and ``surveyor.library.FRAMEWORKS`` — declaration
order is meaningful (it is the final ranking tiebreak).

Two seams, deliberately separate:

  all_skills()               the store. Today it returns the catalogue;
                             a Postgres table or a curated index can replace
                             it without touching retrieval.
  retrieve(framework, intent) the ranking. Today it is a deterministic
                             affinity-and-keyword baseline; embedding
                             retrieval can replace its internals later
                             WITHOUT changing callers — same signature,
                             same return shape. That upgrade stays inside
                             the builder path: per the no-ML boundary,
                             nothing here may ever feed a scoring pipeline.

Ranking is transparent on purpose: a skill scores by how well its
``profile_affinity`` tags match the framework (Step 2's shape — role_view,
lead_surface, diagram_forward, verification_nodes) plus whole-word overlap
between the intent text and the skill's tags and name. Ties resolve by
declaration order. Same inputs, same list, every time.

``intent`` is untrusted chat text: it is length-capped, tokenised to
[a-z0-9]+ words, and never interpolated into patterns or queries — a
hostile intent can only fail to match.
"""

from __future__ import annotations

import re

KINDS = ("skill", "connector", "mcp")

# Affinity tags a skill may declare, and what they match in the framework.
# role_view values + lead_surface values + diagram_forward values + the
# evidence flag. Kept in one tuple so a typo in the catalogue fails a test
# instead of silently never matching.
AFFINITY_TAGS = ("graph", "scaffold", "oversight", "balanced",
                 "canvas", "chat", "dashboard",
                 "graph_first", "text_first",
                 "evidence")

_MAX_INTENT = 400          # matches surveyor.types._MAX_TEXT
_DEFAULT_LIMIT = 8
_WORD_RE = re.compile(r"[a-z0-9]+")

# ------------------------------------------------------------- catalogue

# Seeded for the v1 flagship (systems-thinker / canvas) first, with enough
# breadth that oversight- and chat-led frameworks also get sensible pulls.
SKILLS = (
    {"id": "system-map", "name": "System mapper", "kind": "skill",
     "description": "Lay out the parts of a system and how they connect, as nodes and edges.",
     "profile_affinity": ["graph", "canvas", "graph_first"],
     "tags": ["map", "system", "components", "dependencies", "architecture", "diagram"],
     "inputs": ["a system or plan described in prose"],
     "outputs": ["a node-and-edge map"]},

    {"id": "dependency-trace", "name": "Dependency tracer", "kind": "skill",
     "description": "Follow a change through everything upstream and downstream of it.",
     "profile_affinity": ["graph", "canvas", "graph_first"],
     "tags": ["dependencies", "impact", "trace", "upstream", "downstream", "change"],
     "inputs": ["a proposed change and the system map"],
     "outputs": ["the chain of effects, ordered"]},

    {"id": "workflow-decompose", "name": "Workflow decomposer", "kind": "skill",
     "description": "Break a goal into ordered steps, each with a clear owner and hand-off.",
     "profile_affinity": ["graph", "scaffold", "balanced"],
     "tags": ["steps", "plan", "workflow", "decompose", "sequence", "tasks"],
     "inputs": ["a goal"],
     "outputs": ["ordered steps with owners"]},

    {"id": "evidence-audit", "name": "Evidence auditor", "kind": "skill",
     "description": "Check every claim against the source it came from, and cite it.",
     "profile_affinity": ["evidence", "oversight", "graph"],
     "tags": ["evidence", "sources", "claims", "verify", "citations", "audit"],
     "inputs": ["a draft and its source material"],
     "outputs": ["claims with citations"]},

    {"id": "option-compare", "name": "Option comparator", "kind": "skill",
     "description": "Lay options side by side against the criteria that matter.",
     "profile_affinity": ["graph", "dashboard", "balanced"],
     "tags": ["compare", "options", "criteria", "tradeoffs", "decision"],
     "inputs": ["two or more options and the criteria"],
     "outputs": ["a comparison table"]},

    {"id": "report-draft", "name": "Report drafter", "kind": "skill",
     "description": "Write the result up clearly for the reader it is meant for.",
     "profile_affinity": ["chat", "balanced", "oversight", "text_first"],
     "tags": ["report", "write", "draft", "summary", "document"],
     "inputs": ["findings or results"],
     "outputs": ["a written report"]},

    {"id": "status-board", "name": "Status board", "kind": "connector",
     "description": "Pull progress, blockers, and pending decisions into one view.",
     "profile_affinity": ["oversight", "dashboard"],
     "tags": ["status", "progress", "blockers", "decisions", "overview"],
     "inputs": ["running work items"],
     "outputs": ["a live status view"]},

    {"id": "quick-scaffold", "name": "Quick scaffold", "kind": "skill",
     "description": "Stand up a first working version fast, ready to refine.",
     "profile_affinity": ["scaffold", "canvas"],
     "tags": ["prototype", "scaffold", "draft", "first", "version", "fast"],
     "inputs": ["a rough idea"],
     "outputs": ["a working starting point"]},

    {"id": "source-fetch", "name": "Source fetcher", "kind": "connector",
     "description": "Bring in the source material a task needs before work starts.",
     "profile_affinity": ["evidence", "balanced"],
     "tags": ["fetch", "sources", "research", "material", "collect"],
     "inputs": ["what the task needs to know"],
     "outputs": ["collected source material"]},

    {"id": "project-files", "name": "Project files", "kind": "mcp",
     "description": "Read and write the files the workspace is built around.",
     "profile_affinity": ["scaffold", "canvas", "balanced"],
     "tags": ["files", "read", "write", "project", "documents"],
     "inputs": ["file paths"],
     "outputs": ["file contents and edits"]},
)


def all_skills() -> list:
    """The store seam. Returns fresh copies — callers may mutate freely."""
    return [dict(s, profile_affinity=list(s["profile_affinity"]),
                 tags=list(s["tags"]), inputs=list(s["inputs"]),
                 outputs=list(s["outputs"]))
            for s in SKILLS]


# ------------------------------------------------------------- retrieval

def _framework_tags(framework) -> set:
    """The affinity tags this framework 'is'. Defensive reads only."""
    fw = framework if isinstance(framework, dict) else {}
    tags = set()
    for key in ("role_view", "lead_surface", "diagram_forward"):
        v = fw.get(key)
        if isinstance(v, str) and v in AFFINITY_TAGS:
            tags.add(v)
    if fw.get("verification_nodes"):
        tags.add("evidence")
    return tags


def _intent_words(intent) -> set:
    if not isinstance(intent, str):
        return set()
    return set(_WORD_RE.findall(intent[:_MAX_INTENT].lower()))


def retrieve(framework, intent, limit=_DEFAULT_LIMIT) -> list:
    """Deterministic baseline retrieval. Returns [] when nothing matches.

    Scoring, in plain sight:
      +2.0  skill affinity contains the framework's role_view
      +1.5  ... its lead_surface
      +1.0  ... its diagram_forward
      +1.5  'evidence' affinity when the framework surfaces verification
      +0.5  per distinct intent word appearing in the skill's tags or name

    Ties resolve by catalogue declaration order; the result is stable for
    identical inputs by construction (no randomness, no time, no I/O).
    """
    fw = framework if isinstance(framework, dict) else {}
    fw_tags = _framework_tags(fw)
    words = _intent_words(intent)
    try:
        limit = max(0, int(limit))
    except (TypeError, ValueError, OverflowError):   # inf overflows int()
        limit = _DEFAULT_LIMIT

    weights = {"role_view": 2.0, "lead_surface": 1.5, "diagram_forward": 1.0}
    scored = []
    for index, skill in enumerate(all_skills()):
        affinity = set(skill["profile_affinity"])
        score = 0.0
        for key, weight in weights.items():
            v = fw.get(key)
            if isinstance(v, str) and v in affinity and v in fw_tags:
                score += weight
        if "evidence" in affinity and "evidence" in fw_tags:
            score += 1.5
        if words:
            name_words = set(_WORD_RE.findall(skill["name"].lower()))
            overlap = words & (set(skill["tags"]) | name_words)
            score += 0.5 * len(overlap)
        if score > 0:
            scored.append((-score, index, skill))

    scored.sort(key=lambda t: (t[0], t[1]))
    return [dict(s, score=round(-neg, 2)) for neg, _i, s in scored[:limit]]
