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
# route's own name/description truncation. The item cap exists to bound a
# hostile payload's cost, NOT to limit people: the builder puts no ceiling
# on agents/steps, so the cap must sit far above anything a person would
# assemble by hand — and the write path refuses (write_blockers) rather
# than truncates when a definition genuinely exceeds it.
_MAX_TEXT = 400
_MAX_NAME = 120
_MAX_DESCRIPTION = 600
# Instructions are prose people paste; the builder's textareas put no ceiling
# on them, so this cap too must bound hostile payloads rather than people —
# and the write path refuses over-length instructions instead of truncating.
_MAX_INSTRUCTION = 10000
_MAX_ITEMS = 200

# The full top-level contract. validate_definition() keeps nothing outside
# it, so a write of a definition carrying other keys would destroy them —
# write_blockers() names that instead of letting it happen silently.
DEFINITION_KEYS = ("name", "description", "surface", "agents", "tools",
                   "workflow", "futureHooks")

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


# ------------------------------------------------------------- write guard

def write_blockers(raw) -> list:
    """Reasons a *write* of this definition would destroy well-formed data.

    validate_definition() drops malformed parts silently — right for a
    display path, catastrophic for persistence: adversarial review proved a
    plain load→save round-trip deleting stored agents. The write path
    therefore refuses, with a plain-English reason, whenever validation
    would discard something a person (or another surface) stored on
    purpose:

    The rule, stated once: CONTAINERS refuse, ITEMS canonicalise.

    Containers — the definition's top level and its ``workflow`` /
    ``surface`` / ``futureHooks`` sub-objects — are contract surfaces.
    Anything there the contract does not carry is another writer's data or
    a vocabulary the dashboard does not speak, and a save would destroy or
    silently rewrite it, so it refuses:

      * a list longer than the item cap — including a single step's
        ``toolIds`` (truncation would delete the rest);
      * an instruction longer than the instruction cap (people paste
        prose; cutting the tail is losing their work);
      * an agent/tool/step that CARRIES CONTENT (a name, instructions) but
        whose id or agentId validation cannot use — deleting the record
        because its id is unusable throws away the content too, and a
        pre-cap builder minted uncapped name-slugs, so this is reachable
        by ordinary people;
      * unsupported vocabulary VALUES: a tool ``type``, ``surface.type``
        or ``surface.theme`` outside the vocabulary (dropping the object
        or substituting a plausible default would silently change meaning);
      * foreign keys at the top level or inside workflow/surface/
        futureHooks.

    Items — individual agent/tool/step records — are rebuilt from their
    contract fields: foreign sub-keys drop silently, hook flags and
    ``requiresApproval`` coerce by truthiness (the hitl precedent), and
    content-free junk (non-dict entries, bare unusable ids) was never data.

    Returns [] when a write is loss-free. Never raises. Callers guarding an
    *edit* must run this over the STORED definition as well as the incoming
    one: the read path canonicalises, so a client can innocently post back
    a clean-looking payload whose save would still destroy what the row
    actually holds.
    """
    if not isinstance(raw, dict):
        return []                            # degrades to empty; nothing stored is lost
    blockers = []

    def _has_content(item, *fields):
        return any(isinstance(item.get(f), str) and item[f].strip()
                   for f in fields)

    def _agent_has_content(a):
        # role counts only when it differs from the default the
        # canonicaliser would assign anyway.
        role = a.get("role")
        return (_has_content(a, "name", "instructions")
                or (isinstance(role, str) and role.strip()
                    and role.strip() != "custom"))

    def _tool_has_content(t):
        ttype = t.get("type")
        return (_has_content(t, "name")
                or (ttype in TOOL_TYPES and ttype != "custom"))

    def _step_has_content(s):
        # A step's content is not only prose: chosen tools and an approval
        # checkpoint are deliberate too — and silently removing a checkpoint
        # a person set is the one failure this module vows never to allow.
        tool_ids = s.get("toolIds")
        return (_has_content(s, "instruction")
                or (isinstance(tool_ids, list)
                    and any(isinstance(t, str) and t.strip() for t in tool_ids))
                or bool(s.get("requiresApproval")))

    # A container that is PRESENT but not its contract shape is refused
    # outright: validation would discard it wholesale, and whatever content
    # it holds (an LLM's agents-keyed-by-id object, another surface's list-
    # shaped workflow) would vanish with it. The isinstance gates must never
    # mirror what validation accepts, or the guard goes blind exactly where
    # validation destroys.
    for key, label in (("agents", "agents"), ("tools", "tools")):
        v = raw.get(key)
        if isinstance(v, list):
            if len(v) > _MAX_ITEMS:
                blockers.append(f"definition has more than {_MAX_ITEMS} {label}")
        elif v is not None:
            blockers.append(f"definition's {label} are not stored as a list")

    agents = raw.get("agents")
    if isinstance(agents, list):
        for a in agents[:_MAX_ITEMS]:
            if not isinstance(a, dict):
                continue
            if isinstance(a.get("instructions"), str) \
                    and len(a["instructions"].strip()) > _MAX_INSTRUCTION:
                blockers.append(
                    f"an agent's instructions run past {_MAX_INSTRUCTION} characters")
                break
        for a in agents[:_MAX_ITEMS]:
            # not gated on the id being a str: an ABSENT or wrong-typed id
            # fails _clean_id just the same, and the content is what counts.
            if isinstance(a, dict) and not _clean_id(a.get("id")) \
                    and _agent_has_content(a):
                blockers.append("an agent has an id the canvas cannot use")
                break

    tools = raw.get("tools")
    if isinstance(tools, list):
        for t in tools[:_MAX_ITEMS]:
            if not isinstance(t, dict):
                continue
            if _clean_id(t.get("id")) and t.get("type") not in TOOL_TYPES:
                blockers.append(
                    f"tool type {str(t.get('type'))[:40]!r} is not supported")
                break
        for t in tools[:_MAX_ITEMS]:
            if isinstance(t, dict) and not _clean_id(t.get("id")) \
                    and _tool_has_content(t):
                blockers.append("a tool has an id the canvas cannot use")
                break

    workflow = raw.get("workflow")
    if isinstance(workflow, dict):
        foreign = sorted(k for k in workflow if isinstance(k, str) and k != "steps")
        if foreign:
            blockers.append("workflow carries keys the dashboard does not keep: "
                            + ", ".join(k[:40] for k in foreign[:5]))
        steps = workflow.get("steps")
        if not isinstance(steps, list) and steps is not None:
            blockers.append("workflow steps are not stored as a list")
        if isinstance(steps, list):
            if len(steps) > _MAX_ITEMS:
                blockers.append(f"workflow has more than {_MAX_ITEMS} steps")
            for s in steps[:_MAX_ITEMS]:
                if not isinstance(s, dict):
                    continue
                tool_ids = s.get("toolIds")
                if isinstance(tool_ids, list):
                    if len(tool_ids) > _MAX_ITEMS:
                        blockers.append(f"a step lists more than {_MAX_ITEMS} tools")
                        break
                elif tool_ids is not None:
                    blockers.append("a step's tools are not stored as a list")
                    break
            for s in steps[:_MAX_ITEMS]:
                if isinstance(s, dict) and isinstance(s.get("instruction"), str) \
                        and len(s["instruction"].strip()) > _MAX_INSTRUCTION:
                    blockers.append(
                        f"a step's instruction runs past {_MAX_INSTRUCTION} characters")
                    break
            for s in steps[:_MAX_ITEMS]:
                if isinstance(s, dict) and not _clean_id(s.get("agentId")) \
                        and _step_has_content(s):
                    blockers.append("a step names an agent id the canvas cannot use")
                    break
    elif workflow is not None:
        blockers.append("workflow is not stored as an object")

    surface = raw.get("surface")
    if isinstance(surface, dict):
        foreign = sorted(k for k in surface
                         if isinstance(k, str) and k not in ("type", "theme"))
        if foreign:
            blockers.append("surface carries keys the dashboard does not keep: "
                            + ", ".join(k[:40] for k in foreign[:5]))
        stype = surface.get("type")
        if isinstance(stype, str) and stype not in SURFACE_TYPES:
            blockers.append(f"surface type {stype[:40]!r} is not supported")
        elif not isinstance(stype, str) and surface:
            # Validation deletes the whole surface object when its type is
            # absent or unusable — taking a perfectly valid theme with it.
            blockers.append("surface has no usable type")
        theme = surface.get("theme")
        if isinstance(theme, str) and theme not in SURFACE_THEMES:
            blockers.append(f"surface theme {theme[:40]!r} is not supported")
    elif surface is not None:
        blockers.append("surface is not stored as an object")

    hooks = raw.get("futureHooks")
    if isinstance(hooks, dict):
        foreign = sorted(k for k in hooks
                         if isinstance(k, str) and k not in FUTURE_HOOKS)
        if foreign:
            blockers.append("futureHooks carries keys the dashboard does not keep: "
                            + ", ".join(k[:40] for k in foreign[:5]))
    elif hooks is not None:
        blockers.append("futureHooks are not stored as an object")

    unknown = sorted(k for k in raw if isinstance(k, str) and k not in DEFINITION_KEYS)
    if unknown:
        blockers.append("definition carries keys the dashboard does not keep: "
                        + ", ".join(k[:40] for k in unknown[:5]))
    return blockers


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
