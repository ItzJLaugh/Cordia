#!/usr/bin/env python3
"""Export 6S score data to CSV.

Usage:
  python3 backend/sixs/export_csv.py                 # writes /var/lib/cordia/exports/6s-scores-YYYYMMDD-HHMM.csv
  python3 backend/sixs/export_csv.py -               # prints to stdout
  python3 backend/sixs/export_csv.py /path/out.csv   # explicit path

One row per (score, dimension, tier) cell. NULL cells (unmeasured) are exported
as empty strings, not 0 — 0 is a real measurement and must not be conflated.
"""
import csv, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sixs import store  # noqa: E402

DIMS = ["Source", "Success", "Safety", "Steering", "Switch", "Sharpen"]
TIERS = ["foundation", "design", "configuration"]

def fetch():
    dsn = os.environ.get("CORDIA_PG_DSN", "")
    import psycopg2
    with psycopg2.connect(dsn) as c, c.cursor() as cur:
        cur.execute("""
          SELECT s.id, sub.user_ref, sub.source_ref, s.rubric_version,
                 s.score_matrix, s.dimension_composites, s.final_composite,
                 s.scored_at
          FROM scores s JOIN submissions sub ON sub.id = s.submission_id
          ORDER BY s.id
        """)
        return cur.fetchall()

def rows():
    for (sid, learner, src, ver, matrix, comps, final, at) in fetch():
        comps = comps or {}
        # matrix is a 6x3 array: rows=DIMS order, cols=TIERS order
        for di, dim in enumerate(DIMS):
            for ti, tier in enumerate(TIERS):
                cell = None
                try:
                    cell = matrix[di][ti]
                except (TypeError, IndexError):
                    pass
                yield {
                    "score_id": sid,
                    "learner": learner,
                    "source_ref": src or "",
                    "rubric_version": ver,
                    "scored_at": str(at),
                    "dimension": dim,
                    "tier": tier,
                    "cell_score": "" if cell is None else cell,
                    "dimension_composite": "" if comps.get(dim) is None else comps.get(dim),
                    "final_composite": "" if final is None else final,
                }

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else None
    if out is None:
        os.makedirs("/var/lib/cordia/exports", exist_ok=True)
        out = f"/var/lib/cordia/exports/6s-scores-{time.strftime('%Y%m%d-%H%M')}.csv"
    data = list(rows())
    fields = ["score_id","learner","source_ref","rubric_version","scored_at",
              "dimension","tier","cell_score","dimension_composite","final_composite"]
    if out == "-":
        w = csv.DictWriter(sys.stdout, fieldnames=fields)
        w.writeheader(); w.writerows(data)
    else:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader(); w.writerows(data)
        print(f"wrote {len(data)} rows -> {out}")

if __name__ == "__main__":
    main()
