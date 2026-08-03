#!/usr/bin/env python3
"""6S profile compiler — matrix → capability profile.

Stage 1 of the agent-assignment graph. Pure function over the scores table:
takes a learner's latest score matrix and compiles the profile used for
agent team composition (stage 2, agent_manifest).

Strong/weak are rank-ordered among MEASURED dimensions only. NULL cells are
gaps — never treated as weak, never treated as zero.

CLI: python3 backend/sixs/profile_compiler.py <email>
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DIMS = ["Source", "Success", "Safety", "Steering", "Switch", "Sharpen"]
TIERS = ["foundation", "design", "configuration"]


def latest_scores(email):
    """All score rows for a learner, newest first."""
    import psycopg2
    dsn = os.environ.get("CORDIA_PG_DSN", "")
    with psycopg2.connect(dsn) as c, c.cursor() as cur:
        cur.execute("""
          SELECT s.score_matrix, s.dimension_composites, s.final_composite, s.scored_at
          FROM scores s JOIN submissions sub ON sub.id = s.submission_id
          WHERE sub.user_ref = %s ORDER BY s.id DESC
        """, (email,))
        return cur.fetchall()


def compile_profile(email, rows=None):
    """matrix rows → profile dict. rows defaults to latest_scores(email)."""
    if rows is None:
        rows = latest_scores(email)
    if not rows:
        return None

    # merge: latest measurement per dimension wins; gaps stay gaps
    measured = {}   # dim -> composite
    tier_reach = {} # dim -> best tier with a measured cell
    for matrix, comps, final, at in rows:
        for di, dim in enumerate(DIMS):
            if dim in measured:
                continue
            comp = (comps or {}).get(dim)
            if comp is not None:
                measured[dim] = comp
                # best tier with a non-null cell for this dim
                best = None
                for ti in range(len(TIERS) - 1, -1, -1):
                    try:
                        if matrix[di][ti] is not None:
                            best = TIERS[ti]
                            break
                    except (TypeError, IndexError):
                        pass
                tier_reach[dim] = best

    gaps = [d for d in DIMS if d not in measured]
    ranked = sorted(measured.items(), key=lambda kv: kv[1], reverse=True)
    strong = [d for d, _ in ranked[:2]]
    weak = [d for d, _ in ranked[-2:]] if len(ranked) > 2 else []
    tier_ceiling = "unmeasured"
    for t in reversed(TIERS):
        if t in tier_reach.values():
            tier_ceiling = t
            break

    return {
        "learner": email,
        "scores_used": len(rows),
        "latest_final_composite": rows[0][2],
        "measured": {d: round(v, 2) for d, v in measured.items()},
        "strong_dims": strong,
        "weak_dims": weak,
        "gap_dims": gaps,
        "tier_ceiling": tier_ceiling,
        "tier_reach": tier_reach,
    }


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "jackson@cordiacode.com"
    p = compile_profile(email)
    print(json.dumps(p, indent=2) if p else f"no scores for {email}")
