"""Derives marketing strategy recommendations from real data.

Pulls from track_events, mail_outbox, mail_contacts. Returns ranked list of
3 strategies with: title, evidence, expected impact, draft outline.
"""
import os, sys, time
from collections import Counter, defaultdict

sys.path.insert(0, '/opt/cordia/backend')
from cordia_pipeline import DSN, lock, _conn

DAYS_WINDOW = 30


def _query(sql, args=()):
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def _since(days=DAYS_WINDOW):
    return time.time() - days * 86400


# ---- diagnostics ----

def signup_funnel(days=DAYS_WINDOW):
    rows = _query('''
      SELECT kind, count(DISTINCT anon) AS n FROM track_events
      WHERE ts > %s AND kind IN ('page_view','signup_started','signup_verified',
                                 'exam_started','exam_finished','exam_passed','purchase')
      GROUP BY kind
    ''', (_since(days),))
    d = {k: 0 for k in ('page_view','signup_started','signup_verified',
                         'exam_started','exam_finished','exam_passed','purchase')}
    for k, n in rows: d[k] = n
    return d


def page_top(days=DAYS_WINDOW, limit=8):
    rows = _query('''
      SELECT path, count(*) AS n FROM track_events
      WHERE ts > %s AND kind='page_view' AND path <> ''
      GROUP BY path ORDER BY n DESC LIMIT %s
    ''', (_since(days), limit))
    return [(p, n) for p, n in rows]


def referrers(days=DAYS_WINDOW, limit=8):
    rows = _query('''
      SELECT COALESCE(NULLIF(ref,''),'(direct)') AS src, count(*) AS n
      FROM track_events
      WHERE ts > %s AND kind='page_view'
      GROUP BY src ORDER BY n DESC LIMIT %s
    ''', (_since(days), limit))
    return [(s, n) for s, n in rows]


def email_performance(days=DAYS_WINDOW):
    sent = _query('''SELECT count(*) FROM mail_outbox WHERE sent > %s AND status='sent' ''',
                  (_since(days),))[0][0]
    by_kind_rows = _query('''SELECT kind, count(*) FROM mail_outbox
                             WHERE sent > %s AND status='sent'
                             GROUP BY kind ORDER BY count(*) DESC''',
                           (_since(days),))
    # Be tolerant of either (kind, n) or single-column shape
    by_kind = []
    for row in by_kind_rows:
        if len(row) >= 2:
            by_kind.append((row[0], row[1]))
        else:
            by_kind.append((str(row[0]), 0))
    return {'sent': sent, 'by_kind': by_kind}


def email_open_rate(days=DAYS_WINDOW):
    """Open rate per kind = distinct opens across all sends / total recipients sent.
    Returns dict[kind] = (rate, sends). rate is fraction 0..1+."""
    rows = _query('''
      SELECT mo.kind, count(DISTINCT (mo.send_id, mo.to_email)) AS recipients,
             count(DISTINCT (o.send_id, o.anon)) AS opens
      FROM mail_outbox mo
      LEFT JOIN track_opens o
        ON o.send_id = mo.send_id
       AND o.day > (now() AT TIME ZONE 'UTC')::date - %s::int
      WHERE mo.sent > (now() AT TIME ZONE 'UTC')::date - %s::int
        AND mo.status = 'sent'
        AND mo.send_id IS NOT NULL
      GROUP BY mo.kind
    ''', (days, days))
    out = {}
    for kind, recipients, opens in rows:
        out[kind] = (round(opens / max(recipients, 1), 3), int(recipients))
    return out


def contact_health():
    rows = _query('''SELECT
        count(*) FILTER (WHERE TRUE) AS total,
        count(*) FILTER (WHERE 'exam_taker' = ANY(tags)) AS examined,
        count(*) FILTER (WHERE 'certified' = ANY(tags)) AS certified,
        count(*) FILTER (WHERE 'paying' = ANY(tags)) AS paying,
        count(*) FILTER (WHERE 'abandoned_signup' = ANY(tags)) AS abandoned,
        count(*) FILTER (WHERE updated > %s) AS active_30d
      FROM mail_contacts''', (_since(30),))
    if not rows: return {}
    r = rows[0]
    return {
        'total': r[0], 'examined': r[1], 'certified': r[2],
        'paying': r[3], 'abandoned_signup': r[4], 'active_30d': r[5],
    }


# ---- recommendations ----

def recommend():
    """Top 3 strategies based on data. Pure logic, not vibes."""
    fnl = signup_funnel()
    top_pages = page_top()
    refs = referrers()
    perf = email_performance()
    open_rates = email_open_rate()
    health = contact_health()

    candidates = []

    # 1) Signup→exam conversion
    sv, ex = fnl.get('signup_verified', 0), fnl.get('exam_started', 0)
    if sv >= 5 and ex / max(sv, 1) < 0.30:
        candidates.append({
            'title': 'Close the signup→exam gap with a 24h nudge',
            'evidence': f'{sv} verified signups in the last {DAYS_WINDOW}d, '
                        f'only {ex} ({ex/max(sv,1):.0%}) started the exam.',
            'expected_impact': 'Lifting conversion 30→45% adds '
                                f'{int(sv * 0.15)} new exam starts/mo at zero ad spend.',
            'draft_outline': 'Single email, "Your CordiaAIE exam is waiting", '
                              'links straight to /learn.html, no upsell.',
            'send_class': 'auto_send',
            'priority': 1,
        })

    # 2) Pricing page views but no purchase
    pricing_views = sum(n for p, n in top_pages if 'pricing' in p)
    purchases = fnl.get('purchase', 0)
    if pricing_views >= 50 and purchases < max(pricing_views // 25, 1):
        candidates.append({
            'title': 'Add a pricing-page exit-intent case-study popover',
            'evidence': f'{pricing_views} pricing views vs {purchases} purchases '
                        f'in {DAYS_WINDOW}d — high intent, low close.',
            'expected_impact': f'2% lift = {int(pricing_views*0.02)} extra track sales/mo.',
            'draft_outline': 'Short popover with one concrete result (e.g. "this graduate '
                              'shipped their first orchestrator in 3 weeks"). No discount.',
            'send_class': 'web_change',
            'priority': 2,
        })

    # 3) Low-open welcome series
    for kind in ('welcome_1', 'welcome_2', 'welcome_3'):
        if kind in open_rates and open_rates[kind][0] < 0.30:
            rate, n = open_rates[kind]
            candidates.append({
                'title': f'Rewrite {kind} — open rate is {rate:.0%}',
                'evidence': f'{kind} sent {n} times, opens {rate:.0%}. '
                            'Industry baseline for education is ~38%.',
                'expected_impact': '10-point open-rate lift improves welcome→exam CTR '
                                    'proportionally; cheapest growth lever available.',
                'draft_outline': 'Try a question-based subject ("What kind of orchestrator '
                                  'are you?"). Test 2 variants, pick winner at 48h.',
                'send_class': 'reach_draft',
                'priority': 3,
            })
            break

    # 4) Re-engagement for inactive
    inactive = max(health.get('total', 0) - health.get('active_30d', 0), 0)
    if inactive >= 20:
        candidates.append({
            'title': f'Re-engage {inactive} dormant learners (one email)',
            'evidence': f'{inactive} accounts with no activity in 30d. '
                        'Free quota covers 20/mo; prioritize paying first.',
            'expected_impact': '5% reactivation = '
                                f'{int(inactive*0.05)} re-engaged learners/mo, '
                                'measurable downstream exam starts.',
            'draft_outline': 'Subject: "Still thinking about CordiaAIE?". Body: one paragraph, '
                              'one button to /learn.html. No sequence.',
            'send_class': 'reach_draft',
            'priority': 4,
        })

    # 5) Referral source with momentum
    top_ref = refs[0] if refs else ('(direct)', 0)
    if top_ref[0] not in ('(direct)', '') and top_ref[1] >= 30:
        candidates.append({
            'title': f'Double down on {top_ref[0]} (your top referrer)',
            'evidence': f'{top_ref[1]} visits in {DAYS_WINDOW}d from {top_ref[0]}. '
                        f'Next two referrers: {refs[1] if len(refs)>1 else "n/a"}.',
            'expected_impact': 'A pinned post or focused landing page on this channel '
                                'typically returns 1.5–3× current volume.',
            'draft_outline': 'Repurpose the top-3 most-viewed pages into a single '
                              f'{top_ref[0]}-specific landing page with one CTA.',
            'send_class': 'web_change',
            'priority': 5,
        })

    candidates.sort(key=lambda c: c['priority'])
    return candidates[:3], {
        'funnel': fnl, 'top_pages': top_pages, 'referrers': refs,
        'email': perf, 'open_rates': open_rates, 'health': health,
    }
