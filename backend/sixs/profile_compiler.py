#!/usr/bin/env python3
"""6S profile compiler — matrix → capability profile.

Stage 1 of the agent-assignment graph. Pure function over the scores table:
takes a learner's latest score matrix and compiles the profile used for
agent team composition (stage 2, agent_manifest).

Dimensions are classified against ABSOLUTE thresholds, never against each
other. NULL cells are gaps — never treated as low, never treated as zero.

WHY NOT RANK
------------
This compiler used to take the top two measured dimensions as strong and the
bottom two as developing, by rank. Ranking with no absolute threshold
manufactures a result out of noise: a learner scoring 95 on everything still
came back with two dimensions named as their weakest, and one scoring 30 on
everything still came back with two named as strengths. `surveyor/identifiers.py`
was written specifically to make that failure impossible on the Surveyor side;
this module is the other half of the same fix.

The thresholds below are a judgement call and are not validated against human
grades — no rubric in this package is yet. They are absolute so that a
classification means the same thing for every learner, which ranking never did.

CLI: python3 backend/sixs/profile_compiler.py <email>
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DIMS = ["Source", "Success", "Safety", "Steering", "Switch", "Sharpen"]
TIERS = ["foundation", "design", "configuration"]

# Composites arrive on the scorer's native 0-100 scale.
#
# A dimension at or above STRONG_FLOOR is named as a strength. One below
# DEVELOPING_CEILING is "still developing" — a stage, not a deficit, and the
# only thing it changes downstream is that its agent gets a human checkpoint.
# Everything between the two is simply measured, and is named neither way.
# Provisional until the kappa study gives these numbers something to sit on.
STRONG_FLOOR = 70.0
DEVELOPING_CEILING = 50.0


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
    # Absolute, not relative. Both lists may be empty, and both may be full —
    # that is the point. Order within each is by score for readability only.
    ranked = sorted(measured.items(), key=lambda kv: kv[1], reverse=True)
    strong = [d for d, v in ranked if v >= STRONG_FLOOR]
    developing = [d for d, v in ranked if v < DEVELOPING_CEILING]
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
        "developing_dims": developing,
        # Deprecated alias. assessment.html still reads weak_dims; it is kept
        # pointing at the same list so the page keeps working while the name
        # moves. Remove once no frontend reads it.
        "weak_dims": developing,
        "gap_dims": gaps,
        "thresholds": {"strong_floor": STRONG_FLOOR,
                       "developing_ceiling": DEVELOPING_CEILING,
                       "basis": "absolute, not ranked"},
        "tier_ceiling": tier_ceiling,
        "tier_reach": tier_reach,
    }


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "jackson@cordiacode.com"
    p = compile_profile(email)
    print(json.dumps(p, indent=2) if p else f"no scores for {email}")
