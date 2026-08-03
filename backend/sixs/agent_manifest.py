#!/usr/bin/env python3
"""Agent manifest compiler — capability profile → assigned agentic system.

Stage 2 of the assignment graph. The decision tree is DATA (AGENT_CATALOG),
not code: each 6S dimension maps to an agent with skills, context locations,
database connections, MCP endpoints, RAG pipelines, and hop budget.

Assignment rules (from the orchestration model):
  strong dim  → agent ACTIVE, full autonomy within its lane
  weak dim    → agent ACTIVE but with a mandatory human-checkpoint skill
  gap dim     → agent SHADOW — observes and logs, never acts, until evidence
  tier ceiling → hop budget: foundation=5, design=8, configuration=10

Industries (user-supplied) narrow context: each industry adds RAG sources and
API endpoints relevant to that domain without changing the tree itself.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sixs.profile_compiler import compile_profile  # noqa: E402

HOPS = {"foundation": 5, "design": 8, "configuration": 10, "unmeasured": 5}

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


def build_manifest(profile, industries=None):
    """profile (from compile_profile) + industries → full system manifest."""
    if not profile:
        return None
    industries = [i for i in (industries or []) if i in INDUSTRIES]
    hops = HOPS.get(profile["tier_ceiling"], 5)
    strong, weak, gaps = set(profile["strong_dims"]), set(profile["weak_dims"]), set(profile["gap_dims"])

    agents = []
    for dim, spec in AGENT_CATALOG.items():
        if dim in strong:
            mode, skills = "active", list(spec["skills"])
        elif dim in weak:
            mode, skills = "active-checkpoint", spec["skills"] + ["human-checkpoint"]
        elif dim in gaps:
            mode, skills = "shadow", ["observe", "log-only"]
        else:
            mode, skills = "active", list(spec["skills"])

        a = {
            "dimension": dim,
            "agent": spec["name"],
            "role": spec["role"],
            "mode": mode,
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
