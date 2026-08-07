#!/usr/bin/env python3
"""Agent manifest compiler — capability profile → assigned agentic system.

Stage 2 of the assignment graph. The decision tree is DATA (AGENT_CATALOG),
not code: each 6S dimension maps to an agent with skills, context locations,
database connections, MCP endpoints, RAG pipelines, and hop budget.

WHO DECIDES WHAT
----------------
Two sources feed this, and they have separate jobs. Mixing them is what made
the old version contradict the Surveyor.

  The survey decides BEHAVIOUR.  How much rope each agent gets, and where a
  human has to look, comes from how the person said they work — and, where a
  stage-2 scenario contradicted them, from what they actually chose. This is
  the product's answer to "how should my setup run", and it is authoritative.

  The exam decides REACH.  The 6S matrix sets the tier ceiling and hop budget,
  and marks a dimension SHADOW when there is no measurement behind it. It never
  decides how much oversight a person needs.

The rule that used to live here — bottom-two dimensions by rank get a mandatory
checkpoint — is gone. It ranked a learner against themselves, so someone strong
across the board was still assigned two supervised agents, and it did that while
`surveyor/identifiers.py` was going to some length to guarantee the opposite.
Absolute thresholds now live in profile_compiler; oversight comes from the
survey.

Industries (user-supplied) narrow context: each industry adds RAG sources and
API endpoints relevant to that domain without changing the tree itself.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sixs.profile_compiler import compile_profile  # noqa: E402

HOPS = {"foundation": 5, "design": 8, "configuration": 10, "unmeasured": 5}

# Which Surveyor criterion speaks for which 6S dimension. Used only to mark an
# agent as foregrounded — something the person already does well, so it is worth
# leaning on — never to mark one as needing supervision.
SURVEYOR_CRITERION_FOR_DIM = {
    "Source":   ("intent_clarity", "domain_specificity"),
    "Success":  ("verification_instinct",),
    "Safety":   ("risk_boundary_awareness",),
    "Steering": ("human_checkpoint_judgment", "constraint_setting"),
    "Switch":   ("delegation_readiness",),
    "Sharpen":  ("gap_detection", "workflow_decomposition"),
}

# A criterion at or above this is treated as something to lean on. Same floor
# the Surveyor uses to decide an identifier is worth naming, so a dimension is
# foregrounded here exactly when the person was told about it there.
FOREGROUND_FLOOR = 0.34

# The two dimensions whose mistakes leave the building. When someone wants one
# checkpoint rather than many, these are where it goes.
EXTERNALLY_CONSEQUENTIAL = ("Safety", "Switch")

AGENT_CATALOG = {
    "Source": {
        "name": "Intake Agent",
        "role": "translates raw asks into precise, falsifiable instructions",
        "skills": ["intent-extraction", "requirement-formalization", "ambiguity-flagging"],
        "context": ["/var/lib/cordia/context/", "intent-library"],
        "rag": ["instruction-corpus", "past-intents"],
        "db": ["postgres:cordia (submissions)"],
        "mcp": [],
        "apis": ["SOUL /soul/task"],
    },
    "Success": {
        "name": "Verification Agent",
        "role": "defines and checks success criteria before anything ships",
        "skills": ["criteria-definition", "output-verification", "falsifiability-checks"],
        "context": ["rubric library", "eval definitions"],
        "rag": ["success-criteria-corpus", "grading-exemplars"],
        "db": ["postgres:cordia (scores, human_grades)"],
        "mcp": [],
        "apis": ["training /train/6s/scores"],
    },
    "Safety": {
        "name": "Gatekeeper Agent",
        "role": "enforces policies, red lines, and approval gates",
        "skills": ["policy-enforcement", "approval-gating", "action-audit"],
        "context": ["/var/lib/cordia/context/ (policy docs)"],
        "rag": ["policy-store"],
        "db": ["postgres:cordia (entitlements, devices)"],
        "mcp": ["mcp:policy-store"],
        "apis": ["HiveBus /hive/message (ethics_block)"],
    },
    "Steering": {
        "name": "Coordinator Agent",
        "role": "designs checkpoints and delegation rules across the mesh",
        "skills": ["checkpoint-design", "delegation-rules", "layer-aware-routing"],
        "context": ["agent manifests", "mesh topology"],
        "rag": ["orchestration-patterns"],
        "db": [],
        "mcp": [],
        "apis": ["SOUL /soul/task", "HiveBus /hive/message"],
    },
    "Switch": {
        "name": "Escalation Agent",
        "role": "detects triggers and hands off to humans at the right moment",
        "skills": ["trigger-detection", "human-handoff", "consequence-triage"],
        "context": ["escalation policies", "contact registry"],
        "rag": ["escalation-precedents"],
        "db": ["postgres:cordia (sessions — human reachability)"],
        "mcp": [],
        "apis": ["HiveBus /hive/message (task_failed)"],
    },
    "Sharpen": {
        "name": "Revision Agent",
        "role": "turns wrong outputs into precise delta instructions",
        "skills": ["delta-analysis", "feedback-loop-design", "recurrence-prevention"],
        "context": ["revision history", "corpus diffs"],
        "rag": ["revision-corpus", "feedback-exemplars"],
        "db": ["postgres:cordia (corpus via submissions)"],
        "mcp": [],
        "apis": ["training /train/respond"],
    },
}

# industry -> extra wiring layered onto every assigned agent
INDUSTRIES = {
    "healthcare": {"rag": ["clinical-guidelines"], "apis": ["HL7/FHIR endpoints"], "context": ["hipaa-baseline"]},
    "legal":      {"rag": ["contract-precedents"], "apis": ["court-filing APIs"], "context": ["privilege-rules"]},
    "finance":    {"rag": ["risk-policies"], "apis": ["market-data", "ledger APIs"], "context": ["sox-baseline"]},
    "construction": {"rag": ["schedule-templates", "safety-codes"], "apis": ["permit APIs"], "context": ["osha-baseline"]},
    "software":   {"rag": ["repo-docs", "api-specs"], "apis": ["github", "ci APIs"], "context": ["sdlc-baseline"]},
    "education":  {"rag": ["curriculum-standards"], "apis": ["sis APIs"], "context": ["ferpa-baseline"]},
    "energy":     {"rag": ["grid-ops-manuals"], "apis": ["scada gateways"], "context": ["nerc-baseline"]},
    "marketing":  {"rag": ["brand-guides", "campaign-history"], "apis": ["ads APIs", "analytics"], "context": ["claims-baseline"]},
    "sales":      {"rag": ["crm-playbooks"], "apis": ["crm APIs"], "context": ["pipeline-baseline"]},
    "hr":         {"rag": ["policy-handbooks"], "apis": ["hris APIs"], "context": ["eeo-baseline"]},
    "supplychain": {"rag": ["vendor-catalogs"], "apis": ["erp/inventory APIs"], "context": ["procurement-baseline"]},
    "public":     {"rag": ["regulation-texts"], "apis": ["civic APIs"], "context": ["foia-baseline"]},
    "trades":     {"rag": ["code-books"], "apis": ["inspection APIs"], "context": ["license-baseline"]},
    "engineering": {"rag": ["spec-sheets"], "apis": ["cad/plm APIs"], "context": ["qa-baseline"]},
    "frontline":  {"rag": ["shift-playbooks"], "apis": ["scheduling APIs"], "context": ["labor-baseline"]},
}


def _oversight_policy(surveyor_profile):
    """Which dimensions get a human checkpoint, decided entirely by the survey.

    Reads the *effective* signals — stage-1 answers with stage-2 scenario
    choices layered over them — because the whole point of the scenarios is that
    what someone does under cost beats what they said in the abstract. Where the
    caller has already applied that override, this just reads the result.

    Returns (set_of_dimensions, reason). An empty set is a legitimate answer.
    """
    signals = (surveyor_profile or {}).get("signals") or {}
    delegation = signals.get("delegation_style")
    risk = signals.get("risk_awareness")

    if delegation == "human_reviews_every_step":
        return set(AGENT_CATALOG), ("You said you review every step, so every agent hands "
                                    "back before it moves on.")
    if delegation == "human_checkpoint_before_final":
        return set(EXTERNALLY_CONSEQUENTIAL), ("You said one look before it's final, so the "
                                               "checkpoint sits where work leaves the building.")
    if delegation == "agent_autonomous":
        if risk == "high":
            return set(EXTERNALLY_CONSEQUENTIAL), ("You'd let it run, but stop for anything "
                                                   "irreversible — so only those two hold a gate.")
        return set(), "You'd let it run. Nothing is gated by default; add a gate where you want one."

    # No delegation answer yet. Default to the cautious end and say so, rather
    # than inventing a preference the person never expressed.
    return set(EXTERNALLY_CONSEQUENTIAL), ("Until the survey covers how you delegate, the two "
                                           "agents that can affect someone else hold a gate.")


def _foregrounded(surveyor_profile):
    """Dimensions the survey says this person already handles well."""
    scores = (surveyor_profile or {}).get("scores") or {}
    out = set()
    for dim, criteria in SURVEYOR_CRITERION_FOR_DIM.items():
        for c in criteria:
            v = scores.get(c)
            if isinstance(v, (int, float)) and v >= FOREGROUND_FLOOR:
                out.add(dim)
                break
    return out


def build_manifest(profile, industries=None, surveyor_profile=None):
    """profile (from compile_profile) + industries → full system manifest.

    `surveyor_profile` is the Surveyor's stored profile and is what decides
    each agent's mode. Without it the manifest still builds — every measured
    dimension runs active, unmeasured ones stay shadow — but it carries
    `survey_led: False` so a caller can tell that oversight was defaulted
    rather than chosen.
    """
    if not profile:
        return None
    industries = [i for i in (industries or []) if i in INDUSTRIES]
    hops = HOPS.get(profile["tier_ceiling"], 5)
    gaps = set(profile["gap_dims"])

    checkpointed, oversight_reason = _oversight_policy(surveyor_profile)
    foreground = _foregrounded(surveyor_profile)

    agents = []
    for dim, spec in AGENT_CATALOG.items():
        # Reach first: with no measurement behind a dimension the agent observes
        # and logs. That is a statement about evidence, not about the person.
        if dim in gaps:
            mode, skills = "shadow", ["observe", "log-only"]
        elif dim in checkpointed:
            mode, skills = "active-checkpoint", spec["skills"] + ["human-checkpoint"]
        else:
            mode, skills = "active", list(spec["skills"])

        a = {
            "dimension": dim,
            "agent": spec["name"],
            "role": spec["role"],
            "mode": mode,
            "lean_on": dim in foreground,
            "skills": skills,
            "context": list(spec["context"]),
            "rag": list(spec["rag"]),
            "db": list(spec["db"]),
            "mcp": list(spec["mcp"]),
            "apis": list(spec["apis"]),
        }
        for ind in industries:
            extra = INDUSTRIES[ind]
            a["rag"] += [f"{ind}:{r}" for r in extra["rag"]]
            a["apis"] += [f"{ind}:{r}" for r in extra["apis"]]
            a["context"] += [f"{ind}:{r}" for r in extra["context"]]
        agents.append(a)

    return {
        "learner": profile["learner"],
        "generated_from": f"{profile['scores_used']} score events, final composite {profile['latest_final_composite']}",
        "tier_ceiling": profile["tier_ceiling"],
        "hop_budget": hops,
        "industries": industries,
        "agents": agents,
        "survey_led": bool(surveyor_profile),
        "oversight_reason": oversight_reason,
        "decided_by": {
            "mode and oversight": "your survey answers",
            "tier ceiling and hop budget": "your CordiaAIE score",
            "shadow": "no measurement yet for that dimension",
        },
        "assignment_logic": {
            "active": "full autonomy in-lane",
            "active-checkpoint": "acts, but every output requires human approval",
            "shadow": "observes and logs only — promoted to active when evidence exists",
        },
    }


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "jackson@cordiacode.com"
    inds = sys.argv[2].split(",") if len(sys.argv) > 2 else []
    print(json.dumps(build_manifest(compile_profile(email), inds), indent=2))
