"""Daily digest — high-level diagnostics, ASCII charts, top-3 strategies."""
import os, sys, time
from datetime import datetime, timezone

sys.path.insert(0, '/opt/cordia/backend')
from marketing.strategies import recommend, signup_funnel, page_top, referrers, email_performance, contact_health, email_open_rate
from marketing.templates import BASE_HTML, _safe_format


def _bar(label, value, max_value, width=24):
    if max_value <= 0: return f'  {label:>22} |'
    filled = max(0, min(width, int(round(value / max_value * width))))
    return f'  {label:>22} |{"█"*filled}{"·"*(width-filled)} {value}'


def _ascii_chart(rows, width=40, height=8):
    """rows: list of (label, value). Returns a vertical-ish chart."""
    if not rows: return '(no data)\n'
    max_v = max((v for _, v in rows), default=0) or 1
    lines = []
    # horizontal bar chart, sorted desc
    for label, v in rows[:8]:
        bar = '█' * max(1, int(round(v / max_v * width)))
        lines.append(f'  {label[:24]:<24} {bar:<{width}} {v}')
    return '\n'.join(lines) + '\n'


def _funnel_chart(funnel):
    """Returns the funnel rows for ASCII."""
    stages = [
        ('page_view',          'visited site'),
        ('signup_verified',    'signed up'),
        ('exam_started',       'started exam'),
        ('exam_finished',      'finished exam'),
        ('exam_passed',        'passed (cert)'),
        ('purchase',           'bought a track'),
    ]
    rows = [(label, funnel.get(k, 0)) for k, label in stages]
    return _ascii_chart(rows)


def render(to_email):
    recs, data = recommend()
    fnl = data['funnel']
    health = data['health']
    opens = data['open_rates']
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    # build ASCII diagnostics block
    diag = []
    diag.append(f'Cordia daily digest — {today} (UTC)\n')
    diag.append('Funnel — last 30 days')
    diag.append(_funnel_chart(fnl))
    diag.append('')
    diag.append('Contact health')
    diag.append(_ascii_chart([
        ('total accounts',   health.get('total', 0)),
        ('active 30d',       health.get('active_30d', 0)),
        ('exam takers',      health.get('examined', 0)),
        ('certified',        health.get('certified', 0)),
        ('paying',           health.get('paying', 0)),
        ('abandoned signup', health.get('abandoned_signup', 0)),
    ]))
    diag.append('')
    diag.append('Top pages')
    diag.append(_ascii_chart(data['top_pages']))
    diag.append('')
    diag.append('Top referrers')
    diag.append(_ascii_chart(data['referrers']))
    diag.append('')
    if opens:
        diag.append('Email open rates')
        diag.append(_ascii_chart([(k, int(v[0]*100)) for k, v in opens.items()]))
        diag.append('')

    diag_text = '\n'.join(diag)

    recs_text = '\n\n'.join(
        f"{i+1}. {r['title']}\n"
        f"   Evidence:    {r['evidence']}\n"
        f"   Impact:      {r['expected_impact']}\n"
        f"   Draft:       {r['draft_outline']}\n"
        f"   Channel:     {r['send_class']}"
        for i, r in enumerate(recs)
    ) or '(insufficient data — needs more activity to recommend)'

    text = f"""Hello Jackson,

{diag_text}

Top 3 recommended marketing strategies for the coming week
==========================================================

{recs_text}

—
Cordia pipeline · {to_email}
Reply STOP to remove from this digest.
"""

    recs_html = ''.join(
        f'<div style="margin:18px 0;padding:16px;border-left:3px solid #5c6b49;background:#fbf8f1">'
        f'<div style="font-family:Inter,sans-serif;font-size:11px;letter-spacing:.18em;color:#7a7a68">'
        f'CHANNEL: {r["send_class"].upper()}</div>'
        f'<div style="font-family:Marcellus,serif;font-size:18px;color:#2d321e;margin:6px 0">{i+1}. {r["title"]}</div>'
        f'<div style="font-family:Inter,sans-serif;font-size:13px;color:#2d321e;margin:4px 0"><b>Evidence:</b> {r["evidence"]}</div>'
        f'<div style="font-family:Inter,sans-serif;font-size:13px;color:#2d321e;margin:4px 0"><b>Expected impact:</b> {r["expected_impact"]}</div>'
        f'<div style="font-family:Inter,sans-serif;font-size:13px;color:#2d321e;margin:4px 0"><b>Draft outline:</b> {r["draft_outline"]}</div>'
        f'</div>'
        for i, r in enumerate(recs)
    ) or '<p><i>Not enough data yet to recommend.</i></p>'

    diag_html = f'''
    <h2 style="font-family:Marcellus,serif;color:#2d321e;font-size:22px">Funnel — last 30 days</h2>
    <pre style="font-family:Menlo,monospace;font-size:12px;background:#fbf8f1;padding:14px;border-radius:6px;color:#2d321e;white-space:pre">{_funnel_chart(fnl)}</pre>

    <h2 style="font-family:Marcellus,serif;color:#2d321e;font-size:22px">Contact health</h2>
    <pre style="font-family:Menlo,monospace;font-size:12px;background:#fbf8f1;padding:14px;border-radius:6px;color:#2d321e;white-space:pre">{_ascii_chart([('total accounts',health.get('total',0)),('active 30d',health.get('active_30d',0)),('exam takers',health.get('examined',0)),('certified',health.get('certified',0)),('paying',health.get('paying',0)),('abandoned signup',health.get('abandoned_signup',0))])}</pre>

    <h2 style="font-family:Marcellus,serif;color:#2d321e;font-size:22px">Top pages</h2>
    <pre style="font-family:Menlo,monospace;font-size:12px;background:#fbf8f1;padding:14px;border-radius:6px;color:#2d321e;white-space:pre">{_ascii_chart(data['top_pages'])}</pre>

    <h2 style="font-family:Marcellus,serif;color:#2d321e;font-size:22px">Top referrers</h2>
    <pre style="font-family:Menlo,monospace;font-size:12px;background:#fbf8f1;padding:14px;border-radius:6px;color:#2d321e;white-space:pre">{_ascii_chart(data['referrers'])}</pre>
    '''

    if opens:
        diag_html += f'''
        <h2 style="font-family:Marcellus,serif;color:#2d321e;font-size:22px">Email open rates</h2>
        <pre style="font-family:Menlo,monospace;font-size:12px;background:#fbf8f1;padding:14px;border-radius:6px;color:#2d321e;white-space:pre">{_ascii_chart([(k, int(v[0]*100)) for k, v in opens.items()])}</pre>
        '''
        diag.append('Email open rates (percentage)')
        diag.append(_ascii_chart([(k, int(v[0]*100)) for k, v in opens.items()]))
        diag.append('')

    body = f'''
    <p style="font-family:Inter,sans-serif;color:#2d321e;font-size:14px">Hello Jackson — here's what's moving on Cordia over the last 30 days, plus the three strategies I'd run this week.</p>
    {diag_html}
    <h2 style="font-family:Marcellus,serif;color:#2d321e;font-size:22px;margin-top:30px">Top 3 recommended strategies</h2>
    {recs_html}
    <p style="font-family:Inter,sans-serif;color:#9a9a8a;font-size:12px;margin-top:30px">
      Cordia pipeline · auto-generated · <a href="https://cordiacode.com" style="color:#7a7a68">cordiacode.com</a>
    </p>
    '''
    html = BASE_HTML.format(subject='Your Cordia digest', body=body,
                             unsubscribe_url='https://cordiacode.com/u?email=' + to_email)

    return {
        'to': to_email,
        'subject': f'Cordia digest — {today}',
        'text': text,
        'html': html,
    }


def render_and_send(to_email):
    out = render(to_email)
    import cordia_email as em
    result = em.send(out['to'], out['subject'], out['text'],
                     html=out['html'], kind='daily_digest', tags=['digest','founder'])
    return {'sent': result, 'subject': out['subject']}
