#!/usr/bin/env python3
"""Profile -> workspace defaults, and the personalization kill switch.

Every function here answers the same question: given what we know about this
person, what should their builder look like before they touch anything? The
answer must always be a *default*, never a lock — the user can change any of it
in the builder, and nothing here restricts what they may build.

THE KILL SWITCH
---------------
Resolution order, re-checked on every call:

  1. PERSONALIZATION_MODE=off   -> generic defaults, profile ignored entirely
  2. profile.simple_mode_forced -> simple mode for that one user
  3. simple (the default)       -> explicit fields + the rules below
  4. adaptive                   -> reserved; calls simple and returns

The env var is read with os.environ.get *at call time*, never captured into a
module constant, so flipping it takes a restart rather than a redeploy. The
per-user flag needs neither — it is a column, and the toggle in the builder
writes it live.
"""

from __future__ import annotations

import os

MODES = ("off", "simple", "adaptive")

GENERIC = {
    "surface": {"type": "chat", "theme": "minimal"},
    "agents": [
        {"id": "assistant", "name": "Assistant", "role": "general",
         "instructions": "Help the user with the task they describe."},
    ],
    "tools": [
        {"id": "summarize", "name": "Summarizer", "type": "summarize"},
    ],
    "personalized": False,
    "reason": "Personalization is off. These are Cordia's standard defaults.",
}


def mode() -> str:
    """Current global mode. Unknown values fall back to simple rather than
    failing — a typo in the env file must not take personalization to a state
    nobody designed."""
    m = (os.environ.get("PERSONALIZATION_MODE") or "simple").strip().lower()
    return m if m in MODES else "simple"


def effective_mode(profile) -> str:
    m = mode()
    if m == "off":
        return "off"
    if (profile or {}).get("simple_mode_forced"):
        return "simple"
    return m


# --------------------------------------------------------------- catalogues

_AGENTS = {
    "intake":     {"name": "Intake", "role": "clarify",
                   "instructions": "Restate the request and name anything it leaves open before work starts."},
    "verifier":   {"name": "Verifier", "role": "check",
                   "instructions": "Check claims against the source material and flag anything unsupported."},
    "evidence":   {"name": "Evidence Checker", "role": "check",
                   "instructions": "For each conclusion, cite the specific input it came from."},
    "assumption": {"name": "Assumption Mapper", "role": "analyze",
                   "instructions": "List what the answer assumes, and which assumptions matter most."},
    "comparison": {"name": "Comparison Agent", "role": "analyze",
                   "instructions": "Lay options side by side against the criteria that matter."},
    "reporter":   {"name": "Report Drafter", "role": "draft",
                   "instructions": "Write the result up clearly for the intended reader."},
    "status":     {"name": "Status Panel", "role": "track",
                   "instructions": "Summarise progress, what's blocked, and what needs a decision."},
    "delegator":  {"name": "Task Delegator", "role": "route",
                   "instructions": "Break the work into tasks and assign each to the right step."},
    "tone":       {"name": "Tone Agent", "role": "communicate",
                   "instructions": "Match the register and warmth the audience expects."},
    "audience":   {"name": "Audience Agent", "role": "communicate",
                   "instructions": "Rewrite for the specific reader, naming what they care about."},
    "objection":  {"name": "Objection Handler", "role": "communicate",
                   "instructions": "Anticipate pushback and answer it before it's raised."},
    "spec":       {"name": "Spec Writer", "role": "draft",
                   "instructions": "Turn the request into a precise, testable specification."},
    "triage":     {"name": "Bug Triage", "role": "analyze",
                   "instructions": "Reproduce, isolate, and rank by user impact."},
    "docs":       {"name": "Docs Agent", "role": "draft",
                   "instructions": "Document what it does, how to run it, and what breaks it."},
    "study":      {"name": "Study Guide", "role": "teach",
                   "instructions": "Explain in steps, then check understanding with a question."},
    "quiz":       {"name": "Quiz Builder", "role": "teach",
                   "instructions": "Write questions that test understanding, not recall of wording."},
    "rubric":     {"name": "Rubric Evaluator", "role": "teach",
                   "instructions": "Score against stated criteria and quote the evidence for each."},
    "followup":   {"name": "Lead Follow-up", "role": "communicate",
                   "instructions": "Draft the next touch based on where the conversation stopped."},
    "callsum":    {"name": "Call Summarizer", "role": "summarize",
                   "instructions": "Capture what was agreed, what was promised, and by when."},
}

_TOOLS = {
    "summarize": {"name": "Summarizer", "type": "summarize"},
    "extract":   {"name": "Extractor", "type": "extract"},
    "compare":   {"name": "Comparator", "type": "compare"},
    "draft":     {"name": "Drafter", "type": "draft"},
    "search":    {"name": "Search", "type": "search"},
    "evidence":  {"name": "Evidence Checker", "type": "custom"},
}

# domain keyword -> (agent ids, tool ids). Matched as substrings on whatever the
# person told us their field is.
_DOMAIN_RULES = (
    (("education", "teach", "school", "tutor", "student", "curricul"),
     ("study", "quiz", "rubric"), ("summarize", "compare")),
    (("software", "engineer", "developer", "it ", "devops", "code", "programming"),
     ("spec", "triage", "docs"), ("extract", "search")),
    (("sales", "account", "revenue", "pipeline", "crm"),
     ("followup", "callsum", "objection"), ("summarize", "draft")),
    (("health", "clinic", "patient", "nurse", "medical"),
     ("verifier", "evidence"), ("extract", "evidence")),
    (("legal", "contract", "compliance", "counsel"),
     ("evidence", "assumption"), ("extract", "compare")),
    (("finance", "account", "audit", "budget"),
     ("evidence", "comparison"), ("compare", "extract")),
)


def _level(profile, name):
    """A signal's value, with any stage-2 choice taking precedence.

    Single point of enforcement for "the scenario wins": a situation with a cost
    attached is better evidence than an answer that was free to give, so where
    both exist the revealed one is what shapes the recommendation. Stage 1 is
    still kept — it is what makes a disagreement legible as a finding — but it
    no longer drives the advice on a dimension a scenario has cross-checked.
    """
    from . import scenarios
    p = profile or {}
    revealed = scenarios.revealed_signals(p)
    if name in revealed:
        return revealed[name]
    return (p.get("signals") or {}).get(name)


def _is_high(profile, name):
    return _level(profile, name) == "high"


# ----------------------------------------------------------------- surface

def surface_defaults(profile) -> dict:
    if effective_mode(profile) == "off":
        return dict(GENERIC["surface"])

    stated = _level(profile, "preferred_workspace")
    if stated in ("canvas", "dashboard", "graph_and_chat", "chat_first"):
        return {"type": "chat" if stated == "chat_first" else stated,
                "theme": _theme(profile)}

    if _is_high(profile, "drawing_preference"):
        return {"type": "canvas", "theme": _theme(profile)}
    if _is_high(profile, "graph_preference"):
        return {"type": "graph_and_chat", "theme": _theme(profile)}
    if _is_high(profile, "verbal_preference"):
        return {"type": "chat", "theme": _theme(profile)}
    if _is_high(profile, "visual_preference"):
        return {"type": "dashboard", "theme": _theme(profile)}
    return {"type": "chat", "theme": _theme(profile)}


def _theme(profile) -> str:
    density = _level(profile, "interface_density")
    if density == "detailed":
        return "data"
    if density == "minimal":
        return "minimal"
    if _is_high(profile, "graph_preference") or _is_high(profile, "drawing_preference"):
        return "visual"
    return "formal"


# ------------------------------------------------------------ agents/tools

def suggested_agents(profile) -> list:
    if effective_mode(profile) == "off":
        return list(GENERIC["agents"])

    picks, role = [], _level(profile, "role_tendency")
    if role == "analyzer":
        picks += ["evidence", "assumption", "comparison"]
    elif role == "manager":
        picks += ["status", "delegator"]
    elif role == "human_facing":
        picks += ["tone", "audience", "objection"]
    elif role == "prototyper":
        picks += ["intake", "spec"]
    elif role == "technical_specialist":
        picks += ["spec", "verifier"]

    domain = (_level(profile, "domain") or "").lower()
    for keys, agents, _tools in _DOMAIN_RULES:
        if any(k in domain for k in keys):
            picks += list(agents)
            break

    if _is_high(profile, "risk_awareness"):
        picks.append("verifier")
    if not picks:
        picks = ["intake", "reporter"]

    seen, out = set(), []
    for p in picks:
        if p in _AGENTS and p not in seen:
            seen.add(p)
            out.append(dict(_AGENTS[p], id=p))
    return out[:5]


def suggested_tools(profile) -> list:
    if effective_mode(profile) == "off":
        return list(GENERIC["tools"])

    picks = ["summarize"]
    if _is_high(profile, "graph_preference"):
        picks.append("compare")
    if _level(profile, "verification_preference") == "evidence_first":
        picks.append("evidence")

    domain = (_level(profile, "domain") or "").lower()
    for keys, _agents, tools in _DOMAIN_RULES:
        if any(k in domain for k in keys):
            picks += list(tools)
            break

    seen, out = set(), []
    for p in picks:
        if p in _TOOLS and p not in seen:
            seen.add(p)
            out.append(dict(_TOOLS[p], id=p))
    return out[:5]


def starter_templates(profile) -> list:
    """Named starting points. Generic set when personalization is off."""
    if effective_mode(profile) == "off":
        return [{"id": "blank", "name": "Blank interface",
                 "description": "Start from nothing and add your own agents."}]

    out = [{"id": "blank", "name": "Blank interface",
            "description": "Start from nothing and add your own agents."}]
    role = _level(profile, "role_tendency")
    if role == "analyzer":
        out.append({"id": "analysis", "name": "Analysis workspace",
                    "description": "Intake, evidence check, and a written result."})
    if role == "manager":
        out.append({"id": "oversight", "name": "Oversight workspace",
                    "description": "Task routing with an approval step before anything final."})
    if _is_high(profile, "graph_preference") or _is_high(profile, "drawing_preference"):
        out.append({"id": "visual", "name": "Visual workspace",
                    "description": "Graph and chat side by side, structure first."})
    return out


# -------------------------------------------------------- builder defaults

def builder_defaults(profile) -> dict:
    """Everything the builder needs to lay itself out, plus a plain-language
    reason. The reason is shown to the user — personalization the person cannot
    see the basis for is indistinguishable from the product being weird at them."""
    eff = effective_mode(profile)
    if eff == "off":
        return dict(GENERIC, mode=eff)

    # adaptive is reserved. It calls simple and returns.
    # TODO(adaptive): LLM-assisted layout suggestions, gated behind the same
    # kill switch, only once the simple rules are shown to be insufficient.

    agents = suggested_agents(profile)
    tools = suggested_tools(profile)
    surface = surface_defaults(profile)

    workflow = {"steps": [
        {"id": f"s{i+1}", "agentId": a["id"], "toolIds": [t["id"] for t in tools[:1]],
         "instruction": a["instructions"],
         "requiresApproval": bool(_is_high(profile, "risk_awareness")) and i == len(agents) - 1}
        for i, a in enumerate(agents)
    ]}

    return {
        "mode": eff,
        "surface": surface,
        "agents": agents,
        "tools": tools,
        "workflow": workflow,
        "templates": starter_templates(profile),
        "personalized": True,
        "reason": _reason(profile, surface),
    }


def _reason(profile, surface) -> str:
    bits = []
    # An explicitly chosen workspace outranks anything inferred, so say that
    # first. Without it the reason can read incoherently — citing visual
    # thinking while recommending a plain chat, because the person asked for a
    # plain chat and that (rightly) won.
    stated = _level(profile, "preferred_workspace")
    if stated:
        bits.append("you asked for " + {
            "chat_first": "a clean chat",
            "dashboard": "a dashboard",
            "canvas": "a canvas",
            "graph_and_chat": "a graph beside the chat",
            "balanced": "a balanced mix",
        }.get(stated, "that layout"))
    elif _is_high(profile, "graph_preference") or _is_high(profile, "drawing_preference"):
        bits.append("you think visually")
    if _is_high(profile, "verbal_preference"):
        bits.append("you think by talking things through")
    role = _level(profile, "role_tendency")
    if role and role not in ("unknown", "mixed"):
        bits.append(f"you work like {'an' if role[0] in 'aeiou' else 'a'} {role.replace('_', '-')}")
    if _is_high(profile, "risk_awareness"):
        bits.append("you want a human checkpoint before anything final")
    # Only name the field when the answer is a short noun phrase — see
    # recommendation.short_domain for why truncating a sentence reads as a bug.
    from .recommendation import short_domain
    short = short_domain(_level(profile, "domain"))
    if short:
        bits.append(f"your work is in {short}")

    if not bits:
        return "Cordia's standard starting point. Talk to Surveyor to shape it around you."
    if len(bits) == 1:
        return f"Shaped because {bits[0]}."
    return "Shaped because " + ", ".join(bits[:-1]) + f", and {bits[-1]}."


def soft_profile(profile) -> dict:
    """The small, presentation-only slice handed to the runtime. Never scores,
    never identifiers — the model shapes its output, it does not learn about
    the person."""
    if effective_mode(profile) == "off":
        return {}
    s = (profile or {}).get("signals") or {}
    return {k: s[k] for k in ("preferred_workspace", "interface_density",
                              "verbal_preference", "graph_preference") if k in s}
