#!/usr/bin/env python3
"""Interface Definition shape, vocabularies, and validation.

This formalises the contract the rest of Cordia already speaks informally:
``surveyor_interfaces.definition`` is a JSONB blob whose de facto shape is
built by ``surveyor.adaptation.builder_defaults`` and the web builder —

    agents          the workers ("agents are nodes")
    workflow.steps  the ordered work ("steps in order are the edges")
    requiresApproval a human interrupt on a step

— see the docstrings in ``surveyor.langgraph_adapter`` and
``surveyor.hitl_policy``. Nothing in the existing code validates that blob;
this module is where the dashboard does, so everything downstream (routes,
canvas, runtime) can rely on the shape instead of defending against it.

Validation follows ``surveyor.types`` discipline exactly: everything is an
allow-list, and malformed parts are dropped silently rather than raised —
a model or a hostile client that invents a key must cost us that part, never
the request. A definition that survives validation:

  * has ``agents``, ``tools`` and ``workflow.steps`` lists (possibly empty),
    every item fully cleaned; duplicate declared ids are repaired by
    deterministic suffixing (``checker``, ``checker-2``, …) rather than by
    deleting the later item — a person's second agent must not vanish
    because it shares a display name with the first;
  * keeps steps whose ``agentId`` / ``toolIds`` entries are *well-formed*
    even when nothing declares them. Dangling references are legal in the
    wild — the web builder re-mints ids from display names at save time
    without remapping its steps, so the most common stored definitions
    reference agents by an older id — and the existing renderer falls back
    to the raw id rather than dropping the step. Formalising the contract
    means matching that, not silently deleting people's workflows;
    ``as_graph`` resolves the dangle with a placeholder node the same way.
    Malformed references (wrong type, illegal charset) still cost the part;
  * carries ``name`` / ``description`` / ``surface`` / ``futureHooks`` only
    when the input had a valid one — presentation defaults are the
    adaptation layer's job, not the validator's;
  * is idempotent under re-validation, and a fully-valid definition passes
    through unchanged.

``requiresApproval`` is normalised by *truthiness*, mirroring
``hitl_policy.requires_approval`` (``bool(step.get("requiresApproval"))``).
Truthy strings like ``"false"`` therefore normalise to True — adding an
unwanted checkpoint is the safe failure; silently removing one a person set
is not. The runtime and this validator must never disagree on that call.

Cycles cannot exist in the stored shape — the workflow is an ordered list,
not a free edge set. The graph *projection* (``as_graph``) may legitimately
revisit an agent (A → B → A); renderers must tolerate that, but there is no
cyclic-reference hazard to validate away.
"""

from __future__ import annotations

import re

# ------------------------------------------------------------- vocabularies

# Surface types as produced by adaptation.surface_defaults (stated workspace
# preferences map "chat_first" -> "chat" there, so "chat_first" never appears
# inside a definition).
SURFACE_TYPES = ("chat", "dashboard", "canvas", "graph_and_chat")

# Themes as produced by adaptation._theme.
SURFACE_THEMES = ("minimal", "formal", "visual", "data")

# Tool types as offered by the web builder and adaptation._TOOLS.
TOOL_TYPES = ("summarize", "extract", "compare", "draft", "search", "custom")

# The forward-compatibility flags the web builder stamps on new definitions.
FUTURE_HOOKS = ("langGraphCompatible", "cordiaCompilerCompatible",
                "durableStateReady", "humanInLoopReady")

# Caps. Text caps match surveyor.types._MAX_TEXT and the /surveyor/interface
# route's own name/description truncation; item caps are far above anything
# the builder produces while keeping a hostile payload's cost bounded.
_MAX_TEXT = 400
_MAX_NAME = 120
_MAX_DESCRIPTION = 600
_MAX_INSTRUCTION = 2000
_MAX_ITEMS = 40

# Ids reach DOM attributes, React keys and store lookups; the safe charset is
# the same spirit as the shell's escUrl. First char alphanumeric, then up to
# 199 of [A-Za-z0-9._-] — the builder mints ids by slugging free-text display
# names with no cap of its own, so the cap here must comfortably clear any
# name a person would actually type while still bounding hostile input.
# \Z, not $: $ would tolerate a trailing newline.
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")

# Edge source sentinel for the first step in the graph projection: the first
# step's work has no prior agent to arrive from.
START = "__start__"


# --------------------------------------------------------------- primitives

def _clean_text(v, cap=_MAX_TEXT):
    if not isinstance(v, str):
        return None
    # Strip again after slicing: if the cap lands on whitespace, the first
    # pass would emit text a second pass then strips — re-validation must be
    # a fixed point, not a slow trim.
    v = v.strip()[:cap].strip()
    return v or None


def _clean_id(v):
    if not isinstance(v, str):
        return None
    v = v.strip()
    return v if _ID_RE.match(v) else None


def empty_definition() -> dict:
    """The canonical minimum: the graph contract with nothing in it.

    Deliberately carries no surface/theme — a *safe* empty shape is this
    module's job, a *sensible default* shape is adaptation's.
    """
    return {"agents": [], "tools": [], "workflow": {"steps": []}}


def _unique_id(base, seen, declared, counters) -> str:
    """Deterministic repair for a duplicate declared id: checker, checker-2,
    checker-3…

    The candidate must dodge ``declared`` — every cleaned id anywhere in the
    incoming list — as well as ``seen``: a repair that takes an id a *later*
    item legitimately owns would silently rebind that id's step references
    to the wrong item, which is exactly the corruption this module exists to
    prevent. The declared owner always keeps its id.

    A reference to the still-ambiguous base id binds to the first occurrence
    after repair. That is this module's dedup discipline throughout, chosen
    for stability — on the raw blob today's renderer happens to resolve the
    ambiguity last-wins, but an ambiguous reference has no faithful answer,
    only a deterministic one.

    ``counters`` memoises, per base, where the last repair's search ended.
    Candidates below that point stay blocked forever (``declared`` is fixed
    and ``seen`` only grows), so resuming there changes nothing about the
    output — it only stops a hostile suffix-ladder payload (40 duplicates
    against a 100k-id a-2…a-100k ladder) from costing quadratic rescans of
    CPU on the 2-core host."""
    if base not in seen:
        return base
    n = counters.get(base, 2)
    while True:
        suffix = f"-{n}"
        candidate = base[:200 - len(suffix)] + suffix
        n += 1
        if candidate not in seen and candidate not in declared:
            counters[base] = n
            return candidate


# --------------------------------------------------------------- validation

def _validate_agents(raw) -> list:
    if not isinstance(raw, list):
        return []
    # declared spans the FULL list, not just the emitted first _MAX_ITEMS:
    # a repair must not take an id a beyond-cap item declares either, or a
    # step referencing it would silently bind to the repaired duplicate
    # instead of dangling to a placeholder. One linear pass; the request
    # body cap upstream bounds it.
    declared = {i for i in (_clean_id(a.get("id")) for a in raw
                            if isinstance(a, dict)) if i}
    out, seen, counters = [], set(), {}
    for a in raw[:_MAX_ITEMS]:
        if not isinstance(a, dict):
            continue
        aid = _clean_id(a.get("id"))
        if not aid:
            continue
        aid = _unique_id(aid, seen, declared, counters)
        seen.add(aid)
        out.append({
            "id": aid,
            "name": _clean_text(a.get("name")) or aid,
            "role": _clean_text(a.get("role")) or "custom",
            "instructions": _clean_text(a.get("instructions"), _MAX_INSTRUCTION) or "",
        })
    return out


def _validate_tools(raw) -> list:
    if not isinstance(raw, list):
        return []
    # Full-list declared set for the same reason as _validate_agents.
    declared = {i for i in (_clean_id(t.get("id")) for t in raw
                            if isinstance(t, dict)) if i}
    out, seen, counters = [], set(), {}
    for t in raw[:_MAX_ITEMS]:
        if not isinstance(t, dict):
            continue
        tid = _clean_id(t.get("id"))
        ttype = t.get("type")
        if not tid or ttype not in TOOL_TYPES:
            continue
        tid = _unique_id(tid, seen, declared, counters)
        seen.add(tid)
        out.append({
            "id": tid,
            "name": _clean_text(t.get("name")) or tid,
            "type": ttype,
        })
    return out


def _validate_steps(raw) -> list:
    """Steps keep any *well-formed* reference, declared or not — see the
    module docstring: the wild is full of dangling references the renderer
    already resolves by falling back to the raw id, and deleting a person's
    workflow step is a far worse failure than projecting a placeholder."""
    if not isinstance(raw, dict):
        return []
    steps = raw.get("steps")
    if not isinstance(steps, list):
        return []
    out, seen_ids = [], set()
    for s in steps[:_MAX_ITEMS]:
        if not isinstance(s, dict):
            continue
        agent_id = _clean_id(s.get("agentId"))
        if not agent_id:
            continue
        raw_tools = s.get("toolIds")
        if not isinstance(raw_tools, list):
            # A string here would char-iterate into phantom single-character
            # references; a non-list costs the whole field.
            raw_tools = []
        step = {
            "agentId": agent_id,
            "toolIds": [t for t in (_clean_id(x) for x in raw_tools[:_MAX_ITEMS])
                        if t],
            "instruction": _clean_text(s.get("instruction"), _MAX_INSTRUCTION) or "",
            # Truthiness on purpose — must agree with hitl_policy forever.
            "requiresApproval": bool(s.get("requiresApproval")),
        }
        sid = _clean_id(s.get("id"))
        if sid and sid not in seen_ids:      # kept when present, never invented;
            seen_ids.add(sid)                # first occurrence wins, duplicates
            step["id"] = sid                 # lose the id, not the step
        out.append(step)
    return out


def _validate_surface(raw):
    if not isinstance(raw, dict):
        return None
    stype = raw.get("type")
    if stype not in SURFACE_TYPES:
        return None
    theme = raw.get("theme")
    return {"type": stype,
            "theme": theme if theme in SURFACE_THEMES else "minimal"}


def _validate_hooks(raw):
    if not isinstance(raw, dict):
        return None
    out = {k: bool(raw[k]) for k in FUTURE_HOOKS if k in raw}
    return out or None


def validate_definition(raw) -> dict:
    """Canonical, safe form of whatever arrived. Never raises.

    Anything that is not a definition at all degrades to
    ``empty_definition()`` — the caller keeps a working (empty) canvas
    rather than losing the request.
    """
    if not isinstance(raw, dict):
        return empty_definition()

    agents = _validate_agents(raw.get("agents"))
    tools = _validate_tools(raw.get("tools"))
    steps = _validate_steps(raw.get("workflow"))

    out = {"agents": agents, "tools": tools, "workflow": {"steps": steps}}

    name = _clean_text(raw.get("name"), _MAX_NAME)
    if name:
        out["name"] = name
    desc = _clean_text(raw.get("description"), _MAX_DESCRIPTION)
    if desc:
        out["description"] = desc
    surface = _validate_surface(raw.get("surface"))
    if surface:
        out["surface"] = surface
    hooks = _validate_hooks(raw.get("futureHooks"))
    if hooks:
        out["futureHooks"] = hooks
    return out


# --------------------------------------------------------------- projection

def as_graph(definition) -> dict:
    """Project a *validated* definition onto the canvas contract.

    nodes  = the agents, in declaration order — plus a placeholder node
             (``"placeholder": True``, name = the raw id) for every
             well-formed ``agentId`` no agent declares, appended in first-
             reference order. That mirrors the existing renderer, which
             falls back to the raw id rather than dropping the step.
    edges  = one per step, in workflow order: edge *i* is the arrival at
             step *i*'s agent from the previous step's agent (or ``START``
             for the first step), carrying that step's instruction, tools
             and approval flag. Lossless: edge i <-> workflow.steps[i].

    An approval interrupt therefore sits on the edge that *enters* the work
    it gates, which is where the canvas draws it and where a graph runtime
    would place the interrupt.

    Defensive reads only — feeding it an unvalidated blob yields a partial
    projection, never an exception.
    """
    d = definition if isinstance(definition, dict) else {}
    agents = d.get("agents")
    if not isinstance(agents, list):
        agents = []
    nodes = [dict(a) for a in agents
             if isinstance(a, dict) and isinstance(a.get("id"), str) and a.get("id")]

    known = {n["id"] for n in nodes}
    edges, prev = [], START
    steps = (d.get("workflow") or {}).get("steps") if isinstance(d.get("workflow"), dict) else None
    if not isinstance(steps, list):
        steps = []
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            continue
        target = _clean_id(s.get("agentId"))
        if not target:
            continue
        if target not in known:
            # Dangling reference: resolve with a placeholder, exactly like
            # the renderer's fall-back-to-raw-id, so the step stays visible
            # instead of vanishing from the canvas.
            nodes.append({"id": target, "name": target, "role": "custom",
                          "instructions": "", "placeholder": True})
            known.add(target)
        tool_ids = s.get("toolIds")
        edges.append({
            "source": prev,
            "target": target,
            "step": i,
            "instruction": s.get("instruction") or "",
            "toolIds": list(tool_ids) if isinstance(tool_ids, list) else [],
            "requiresApproval": bool(s.get("requiresApproval")),
        })
        prev = target
    return {"nodes": nodes, "edges": edges}
