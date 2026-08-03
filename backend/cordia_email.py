#!/usr/bin/env python3
"""Cordia transactional email — Hostinger Agentic Mail first, Gmail SMTP fallback.

Env (in /etc/cordia/cordia.env):
  AGENTIC_MAIL_TOKEN         Bearer token for api.mail.hostinger.com
  AGENTIC_MAIL_RESOURCE_ID   Mailbox resource ID (format AC...). Get from GET /api/v1/me
  AGENTIC_MAIL_DISPLAY_NAME  Optional displayName on outgoing email
  AGENTIC_MAIL_BASE          Default: https://api.mail.hostinger.com
  TRACKER_DOMAIN             Optional: t.cordiacode.com — used to wrap links for click tracking
  TRACK_OPEN_PIXEL           If "1", append 1x1 open pixel via TRACKER_DOMAIN

Gmail SMTP (GMAIL_USER, GMAIL_APP_PASSWORD) is kept ONLY as fallback when
AGENTIC_MAIL_TOKEN is unset. New code should never depend on Gmail; only
the legacy 2FA code path in cordia_auth.py still touches it until migrated.

Public API:
  send(to, subject, text, html=None, kind='', contact_id=None, tags=None) -> dict
  send_batch(items) -> list[dict]    # list of {to, subject, ...}
  health() -> dict                   # which provider is live
  list_mailboxes() -> dict           # GET /api/v1/me — useful for setup

All sends are logged to /var/lib/cordia/log/email_send.jsonl for audit.
"""
import json, os, smtplib, sys, time, urllib.request, urllib.error
from email.message import EmailMessage

LOG = '/var/lib/cordia/log/email_send.jsonl'
os.makedirs(os.path.dirname(LOG), exist_ok=True)

TOKEN      = os.environ.get('AGENTIC_MAIL_TOKEN', '').strip()
RESOURCE_ID = os.environ.get('AGENTIC_MAIL_RESOURCE_ID', '').strip()
DISPLAY_NAME = os.environ.get('AGENTIC_MAIL_DISPLAY_NAME', '').strip() or 'Cordia'
FROM_      = os.environ.get('AGENTIC_MAIL_FROM', 'Cordia <cordia@cordiacode.com>').strip()
BASE       = os.environ.get('AGENTIC_MAIL_BASE', 'https://api.mail.hostinger.com').rstrip('/')
TRACKER_DOMAIN = os.environ.get('TRACKER_DOMAIN', '').strip()
TRACK_OPEN     = os.environ.get('TRACK_OPEN_PIXEL', '') == '1'

GMAIL_USER = os.environ.get('GMAIL_USER', '').strip()
GMAIL_PW   = os.environ.get('GMAIL_APP_PASSWORD', '').strip()


def _log(rec):
    rec = dict(rec)
    rec['ts'] = time.time()
    with open(LOG, 'a') as f:
        f.write(json.dumps(rec, default=str) + '\n')


def _wrap_links(html, send_id):
    """Rewrite hrefs in HTML to go through TRACKER_DOMAIN/c/<send_id>?u=<url>."""
    if not (TRACKER_DOMAIN and html):
        return html
    import re
    def rep(m):
        url = m.group(1)
        if url.startswith(('mailto:', 'tel:', '#')) or TRACKER_DOMAIN in url:
            return m.group(0)
        from urllib.parse import quote
        return f'href="https://{TRACKER_DOMAIN}/c?id={send_id}&u={quote(url, safe="")}"'
    return re.sub(r'href="([^"]+)"', rep, html)


def _append_pixel(html, send_id):
    if not (TRACKER_DOMAIN and TRACK_OPEN and html):
        return html
    pix = f'<img src="https://{TRACKER_DOMAIN}/o?id={send_id}" width="1" height="1" alt="" style="display:block;border:0;width:1px;height:1px">'
    if '</body>' in html.lower():
        return html.replace('</body>', pix + '</body>', 1)
    return html + pix


def _send_agentic(to, subject, text, html, kind, send_id):
    """POST /api/v1/mailboxes/{mailboxResourceId}/send (Hostinger Agentic Mail API).
    See: https://api.mail.hostinger.com/openapi/openapi.json"""
    if not RESOURCE_ID:
        return {'ok': False, 'provider': 'agentic', 'error': 'AGENTIC_MAIL_RESOURCE_ID not set'}
    body = {
        'to': [to] if isinstance(to, str) else list(to),
        'displayName': DISPLAY_NAME,
        'subject': subject,
        'text': text,
    }
    if html:
        body['html'] = html
    req = urllib.request.Request(
        f'{BASE}/api/v1/mailboxes/{RESOURCE_ID}/send',
        data=json.dumps(body).encode(),
        headers={
            'Authorization': f'Bearer {TOKEN}',
            'Content-Type': 'application/json',
            'User-Agent': 'cordia-pipeline/1.0',
        },
        method='POST',
    )
    try:
        # 204 No Content on success per spec
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode()
            try: payload = json.loads(raw) if raw else {}
            except Exception: payload = {'raw': raw}
            return {'ok': True, 'provider': 'agentic', 'status': r.status, 'payload': payload}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'provider': 'agentic', 'status': e.code, 'error': e.read().decode()[:400]}
    except Exception as e:
        return {'ok': False, 'provider': 'agentic', 'error': str(e)}


def _send_gmail(to, subject, text):
    msg = EmailMessage()
    msg['From'] = GMAIL_USER
    msg['To'] = to
    msg['Subject'] = subject
    msg.set_content(text)
    with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as s:
        s.starttls()
        s.login(GMAIL_USER, GMAIL_PW)
        s.send_message(msg)
    return {'ok': True, 'provider': 'gmail'}


def send(to, subject, text, html=None, kind='', contact_id=None, tags=None):
    """Single transactional send. Returns {ok, provider, send_id, ...}."""
    send_id = f'em_{int(time.time()*1000)}_{abs(hash(to))%10000:04d}'
    if html and TRACKER_DOMAIN:
        html = _wrap_links(html, send_id)
        html = _append_pixel(html, send_id)

    if TOKEN and RESOURCE_ID:
        result = _send_agentic(to, subject, text, html, kind, send_id)
    elif GMAIL_USER and GMAIL_PW:
        try:
            result = _send_gmail(to, subject, text)
        except Exception as e:
            result = {'ok': False, 'provider': 'gmail', 'error': str(e)}
    else:
        result = {'ok': False, 'provider': 'none', 'error': 'no email provider configured (set AGENTIC_MAIL_TOKEN+AGENTIC_MAIL_RESOURCE_ID, or GMAIL_*)'}

    _log({'send_id': send_id, 'to': to, 'subject': subject, 'kind': kind,
          'contact_id': contact_id, 'tags': tags or [], **result})
    return {'send_id': send_id, **result}


def send_batch(items):
    out = []
    for it in items:
        out.append(send(
            it['to'], it['subject'], it['text'],
            html=it.get('html'), kind=it.get('kind', ''),
            contact_id=it.get('contact_id'), tags=it.get('tags'),
        ))
    return out


def health():
    return {
        'agentic_configured': bool(TOKEN and RESOURCE_ID),
        'gmail_fallback': bool(GMAIL_USER and GMAIL_PW),
        'from': FROM_,
        'resource_id_set': bool(RESOURCE_ID),
        'tracker_domain': TRACKER_DOMAIN or None,
        'open_tracking': TRACK_OPEN,
    }


def list_mailboxes():
    """GET /api/v1/me — returns the mailboxes your token can manage.
    Run once after you create the API token to learn the mailbox resourceId
    (format AC...); paste that into AGENTIC_MAIL_RESOURCE_ID.
    """
    if not TOKEN:
        return {'ok': False, 'error': 'AGENTIC_MAIL_TOKEN not set'}
    req = urllib.request.Request(
        f'{BASE}/api/v1/me',
        headers={'Authorization': f'Bearer {TOKEN}', 'User-Agent': 'cordia-pipeline/1.0'},
        method='GET',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return {'ok': True, 'status': r.status,
                    'data': json.loads(r.read().decode())}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'status': e.code, 'error': e.read().decode()[:400]}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('usage: cordia_email.py <to> <subject> <textfile>', file=sys.stderr)
        sys.exit(2)
    text = open(sys.argv[3]).read()
    print(json.dumps(send(sys.argv[1], sys.argv[2], text), indent=2))
