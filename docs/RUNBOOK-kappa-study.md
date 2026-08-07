# Runbook — the two-rater κ study

Every command here is run **by you, on the VPS**. Nothing in this repo connects
to the server on its own.

This is the only evidence CordiaAIE-1's automated scorer works. The certification
is already being sold; until this runs, any claim that the score means something
is unsupported. `CORDIA_BRIEF.md` records the current state as **0 ratings —
never run**.

Nothing here changes what a learner sees. Rating writes to `ratings.jsonl`; no
certificate is recomputed and no score moves.

---

## What the study actually is

Two people grade the same exam answers, independently, without talking. Cohen's
κ measures how much they agreed *after subtracting the agreement you would expect
from chance alone*.

The reasoning is short: if two humans reading the same rubric cannot agree on
what a good answer looks like, the rubric is ambiguous — and an automated scorer
built on an ambiguous rubric cannot be trusted either. High κ does not prove the
scorer is right. Low κ proves it cannot be.

The bar comes from the authoring standard the code already cites (A8):

| | |
|---|---|
| Paired responses | **≥ 100** |
| Cohen's κ | **≥ 0.80** |
| Below that | the rubric is rewritten, not the threshold |

---

## 0. Is there enough data? Read-only, run this first

This reproduces `_rateable_candidates()` exactly — the same collapse rule the
raters and the real scorer both see — so the number it prints is the number of
items available to grade. Paste as one block:

```bash
python3 - <<'PY'
import json, os
D = "/var/lib/cordia/corpus"
def rows(p):
    out = []
    if not os.path.exists(p): return out
    for line in open(p, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line: continue
        try: out.append(json.loads(line))
        except Exception: pass
    return out

corpus  = rows(os.path.join(D, "corpus.jsonl"))
ratings = rows(os.path.join(D, "ratings.jsonl"))

# same rule as _rateable_candidates(): latest non-empty value per (learner, block)
latest = {}
for r in sorted([c for c in corpus if c.get("track") == "aie1" and c.get("block")],
                key=lambda r: r.get("ts", 0)):
    latest[(r.get("learner") or "anon", r.get("block"))] = r
pool = [r for r in latest.values() if (r.get("value") or "").strip()]

per = {}
for r in ratings:
    rid, who = str(r.get("response_id", "")), str(r.get("rater", ""))
    if rid and who in ("A", "B"): per.setdefault(rid, set()).add(who)
paired = [k for k, v in per.items() if len(v) >= 2]

learners = {str(r.get("learner", "")) for r in pool}
print("gradeable items (the pool) :", len(pool))
print("distinct learners in pool  :", len(learners))
print("items with 1 rating        :", sum(1 for v in per.values() if len(v) == 1))
print("items with BOTH raters     :", len(paired), " <- this is n for kappa")
print()
print("need >=100 paired for the A8 standard;",
      "pool is", "sufficient" if len(pool) >= 100 else "TOO SMALL — see section 5")
PY
```

**Read the last line before doing anything else.** If the pool is under 100, no
amount of grading reaches the standard. Go to section 5 first.

---

## 1. Name the two raters

Rater identity is resolved server-side from environment variables and is never
accepted from the browser. Add both to `/etc/cordia/cordia.env`:

```bash
sudo tee -a /etc/cordia/cordia.env >/dev/null <<'ENV'
CORDIA_RATER_A=first.rater@example.com
CORDIA_RATER_B=second.rater@example.com
ENV
sudo systemctl restart cordia-backend.service
```

Both addresses must already have Cordia accounts — the rater pages sit behind
the normal auth gate, and an email with no account simply cannot sign in.

> **Setting these also grants Surveyor admin access.** `_surv_is_admin()` folds
> `CORDIA_RATER_A/B` into the admin allow-list alongside `CORDIA_ADMINS`, so both
> raters can read `/surveyor/admin` — every profile, transcript and event for any
> user. Pick rater B accordingly, and remove the variable when the study is done
> if that access was not intended.

Confirm it took:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
     https://cordiacode.com/train/rate/queue?limit=1 | head -c 400
```

A `403 this account is not on the rater list` means the email did not match —
check for a typo or trailing whitespace. Matching is case-insensitive and
trimmed, but it is exact otherwise.

---

## 2. Grade — both raters, independently

Each rater signs in and opens:

```
https://cordiacode.com/rate.html
```

The page is `noindex` and absent from the public catalogue by design. It is not
a stray exam — **do not delete it.**

They see one answer at a time with the learner's identity stripped, and pick one
of four levels:

| Level | Means |
|---|---|
| `0-missing` | the thing the question asked for is not there |
| `1-vague` | gestures at it, but nothing checkable |
| `2-specific` | concrete and actionable |
| `3-falsifiable` | stated so you could tell whether it happened |

The queue puts items the *other* rater has already graded at the front, so pairs
complete rather than both raters independently opening new ground. κ only counts
items both people scored; a thousand unpaired ratings produce a κ of nothing.

**The two rules that make the result mean anything:**

1. **No conferring.** Not before, not during, not "just checking how you read
   this one". The moment the raters calibrate to each other, κ measures their
   conversation instead of the rubric.
2. **Rater B must be able to read the rubric cold.** If B has had the intent
   explained to them by whoever wrote the checks, κ comes back high and tells you
   nothing. `aie_map.py` already names this requirement — authorship split from
   whoever wrote the structural check.

Re-rating an item is allowed; the latest rating per (item, rater) wins, the same
collapse rule `_kappa()` and the scorers use.

---

## 3. Read the result

Any time, from either rater's account:

```bash
curl -s -H "Authorization: Bearer $TOKEN" https://cordiacode.com/train/kappa
```

Or finish the queue in `rate.html`, which shows it on completion.

```jsonc
{
  "n_pairs": 104,             // items both raters scored
  "kappa": 0.83,              // the number that matters
  "passed": true,             // kappa >= 0.80
  "threshold": 0.80,
  "candidate_pool_size": 156,
  "confusion": [...],         // diagnostic only
  "per_block": {...}          // diagnostic only
}
```

`"kappa": null` has two distinct causes, and they are not the same problem:

- `n_pairs: 0` — nobody has graded the same item twice yet. Keep going.
- `n_pairs > 0` with a note about expected agreement — every rating was the same
  level, so there is no variance to correct for and κ is mathematically
  undefined. That usually means the sample is too uniform, not that agreement is
  perfect.

---

## 4. What the number means, and what to do

| κ | Reading | Do |
|---|---|---|
| ≥ 0.80 | The rubric is stated clearly enough that two people apply it the same way | Record it. The scorer now has evidence behind it. |
| 0.60 – 0.79 | Real agreement, below the standard | Read `per_block`. Usually one or two blocks carry the disagreement — rewrite those, re-rate only those. |
| < 0.60 | The rubric is ambiguous | Rewrite it before selling another certificate on it. |
| `null` | Undefined, see section 3 | Get more paired items, or a more varied sample. |

`per_block` is the useful part on a failure. It tells you *which* of the twelve
questions the raters read differently, which is a much smaller fix than rewriting
the whole rubric.

**A passing κ validates the rubric, not the scorer.** It says two humans agree on
what the levels mean. Comparing those human levels against
`cordaie_scoring.score_course()` output is the separate, and next, question.

---

## 5. If the pool is too small

Section 0 printed a pool under 100. Grading harder does not fix this — there are
not enough distinct answers to grade.

Two honest options:

**Get more real submissions.** This is the unblock-everything item already at the
top of `CORDIA_BRIEF.md`: put real people through the product. Every new learner
who completes the exam adds up to 12 items to the pool.

**Run it at a smaller n and say so.** A κ over 60 pairs is real evidence and is
much better than none. It is not the A8 standard, and any writeup has to say
which one it is. Do not quietly move the threshold to match the sample.

There is a third thing that looks like an option and is not: most of the current
corpus is test data written during development. Two raters agreeing on answers
you wrote yourself while building the thing tells you the rubric is internally
consistent. It does not tell you the scorer works on real learners. Check how
many distinct learners section 0 reported before deciding what the result is
worth.

---

## 6. Record it

When the study completes, update the data table in `CORDIA_BRIEF.md`:

```
| Rater agreement (κ) | **0 ratings — never run** |
```

Replace with the κ, the n, the date, and the number of distinct learners in the
sample. That last column is what stops the number being over-read later.

Back up the raw ratings before anything else touches them:

```bash
sudo cp /var/lib/cordia/corpus/ratings.jsonl \
        /var/lib/cordia/corpus/ratings-$(date +%F).jsonl.bak
```

Until κ is recorded, section 7 of the brand guide applies without exception: the
score is not "validated", not "proven", and not "accredited". It is a
measurement whose methodology is published — which is a real differentiator, and
a defensible claim on its own.
