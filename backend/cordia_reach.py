"""Hostinger Reach client — contact management only.

Reach API (ground truth from github.com/hostinger/api-mcp-server src/servers/reach.ts):
  Base URL: https://api.hostinger.com
  Auth:     Bearer <HOSTINGER_API_TOKEN> in Authorization header
  12 endpoints total, all under /api/reach/v1/

What we use:
  GET  /api/reach/v1/profiles                           -> list profiles (get profileUuid)
  GET  /api/reach/v1/contacts                           -> list contacts
  POST /api/reach/v1/contacts                           -> create contact {email, name, surname, phone, note}
  DELETE /api/reach/v1/contacts/{uuid}                  -> delete contact
  GET  /api/reach/v1/contacts/groups                    -> list groups
  GET  /api/reach/v1/segmentation/segments              -> list segments
  POST /api/reach/v1/segmentation/segments              -> create segment
  GET  /api/reach/v1/segmentation/segments/{uuid}       -> get segment details
  GET  /api/reach/v1/segmentation/segments/{uuid}/contacts -> list segment contacts

What we do NOT use (no API exists for it):
  - Campaign send (must go through reach.hostinger.com UI)
  - Usage / quota (check reach.hostinger.com UI)
  - Events (Reach tracks opens/clicks internally on its own sends)

Public API:
  upsert_contact(email, attrs=None) -> dict    # POST /api/reach/v1/contacts, idempotent locally
  list_contacts(page=1, group_uuid=None, status=None) -> dict
  delete_contact(uuid) -> bool
  list_profiles() -> dict                      # first call to learn your profileUuid
  list_segments() -> dict
  queue_campaign(...)                          # ALWAYS local draft, no API send
  list_drafts() -> list
  approve_draft(id) -> dict

Usage gates:
  queue_campaign(manual_only=True) writes the campaign draft to
  /var/lib/cordia/marketing/drafts/<id>.json. The operator sends it through
  reach.hostinger.com UI, then runs `cordia-ops pipeline.py approve <id>`
  to archive the draft. There is no API path to send a campaign — this is
  Hostinger's design, not a limitation of our client.
"""
import json, os, sys, time, urllib.request, urllib.error
from urllib.parse import urlencode, quote

API_KEY  = os.environ.get('HOSTINGER_API_TOKEN', '').strip() or os.environ.get('REACH_API_KEY', '').strip()
BASE     = os.environ.get('REACH_BASE', 'https://api.hostinger.com').rstrip('/')
SECRET   = os.environ.get('REACH_WEBHOOK_SECRET', '').strip()  # for /pay/reach-webhook, not Reach API
DRAFTS   = '/var/lib/cordia/marketing/drafts'
os.makedirs(DRAFTS, exist_ok=True)


def _req(method, path, body=None, qs=None):
    """All Reach endpoints live under {BASE}/api/reach/v1/..."""
    url = f'{BASE}/api/reach/v1{path}'
    if qs:
        url += '?' + urlencode({k: v for k, v in qs.items() if v is not None})
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json',
        'User-Agent': 'cordia-pipeline/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode()
            try: return r.status, json.loads(raw) if raw else {}
            except Exception: return r.status, {'raw': raw}
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {'raw': ''}
    except Exception as e:
        return 0, {'error': str(e)}


def _configured():
    if not API_KEY:
        return False, 'HOSTINGER_API_TOKEN (or REACH_API_KEY) not set'
    return True, ''


# ---- Profiles ----
def list_profiles():
    """GET /api/reach/v1/profiles — learn your profileUuid before first use."""
    ok, why = _configured()
    if not ok: return {'ok': False, 'error': why}
    status, payload = _req('GET', '/profiles')
    return {'ok': 200 <= status < 300, 'status': status, 'profiles': payload}


# ---- Contacts ----
def upsert_contact(email, attrs=None):
    """POST /api/reach/v1/contacts with {email, name, surname, phone, note}.
    Reach returns 409 if email already exists — we treat that as success."""
    ok, why = _configured()
    if not ok: return {'ok': False, 'error': why}
    email = email.strip().lower()
    attrs = attrs or {}
    body = {'email': email}
    if attrs.get('first_name'): body['name'] = attrs['first_name']
    if attrs.get('last_name'):  body['surname'] = attrs['last_name']
    if attrs.get('phone'):      body['phone'] = attrs['phone']
    if attrs.get('note'):       body['note'] = attrs['note']
    status, payload = _req('POST', '/contacts', body=body)
    if status in (200, 201): return {'ok': True, 'action': 'created', 'contact': payload}
    if status == 409:        return {'ok': True, 'action': 'exists',  'contact': payload}
    return {'ok': False, 'status': status, 'error': payload}


def list_contacts(page=1, group_uuid=None, subscription_status=None):
    """GET /api/reach/v1/contacts. subscription_status: 'subscribed'|'unsubscribed'."""
    ok, why = _configured()
    if not ok: return {'ok': False, 'error': why, 'contacts': []}
    qs = {'page': page, 'group_uuid': group_uuid, 'subscription_status': subscription_status}
    status, payload = _req('GET', '/contacts', qs=qs)
    if status != 200: return {'ok': False, 'status': status, 'error': payload, 'contacts': []}
    return {'ok': True, 'contacts': payload.get('data', payload.get('contacts', payload))}


def delete_contact(uuid):
    """DELETE /api/reach/v1/contacts/{uuid}. Needs the UUID, not the email."""
    ok, why = _configured()
    if not ok: return False
    if not uuid: return False
    status, _ = _req('DELETE', f'/contacts/{quote(uuid, safe="")}')
    return 200 <= status < 300


# ---- Segments ----
def list_segments():
    ok, why = _configured()
    if not ok: return {'ok': False, 'error': why, 'segments': []}
    status, payload = _req('GET', '/segmentation/segments')
    return {'ok': 200 <= status < 300, 'status': status, 'segments': payload}


# ---- Quota (no API — stub that returns safe defaults) ----
def get_usage():
    """Reach quota is managed in the Reach UI (reach.hostinger.com).
    There is no public API for usage stats. Returns a stub so the digest
    doesn't crash, but operator should check the UI for real numbers."""
    return {
        'ok': True,
        'note': 'no API — check reach.hostinger.com for real usage',
        'emails_used': 0, 'emails_limit': 200,
        'recipients_used': 0, 'recipients_limit': 100,
        'period': '',
    }


def should_throttle(usage, hard_cap_pct=80):
    """With no real usage data, never auto-throttle. Operator decides via UI."""
    return False, 'quota API unavailable — check reach.hostinger.com'


# ---- Campaign drafts (local-only) ----
def queue_campaign(name, subject, html, text, segment=None, manual_only=True, tags=None):
    """ALWAYS writes a draft to disk. Reach has no campaign-send API."""
    cid = f'c_{int(time.time())}_{abs(hash(name))%10000:04x}'
    draft = {
        'id': cid,
        'name': name,
        'subject': subject,
        'html': html,
        'text': text,
        'segment': segment or 'all',
        'tags': tags or [],
        'created': time.time(),
        'manual_only': True,  # always True now — no API path exists
        'status': 'draft',
        'instructions': (
            'Reach has no campaign-send API. Open reach.hostinger.com, '
            'create a new campaign, paste the HTML below into the editor, '
            f'then run: python3 /opt/cordia-ops/pipeline.py approve {cid}'
        ),
    }
    path = os.path.join(DRAFTS, f'{cid}.json')
    with open(path, 'w') as f:
        json.dump(draft, f, indent=2)
    return {'ok': True, 'draft': path, 'id': cid, 'sent_via_reach': False}


def approve_draft(cid):
    """Move a draft from drafts/ to sent/ — call after manual send in Reach UI."""
    src = os.path.join(DRAFTS, f'{cid}.json')
    if not os.path.exists(src): return {'ok': False, 'error': 'not found'}
    with open(src) as f: draft = json.load(f)
    draft['status'] = 'approved'
    draft['approved'] = time.time()
    dst = '/var/lib/cordia/marketing/sent'
    os.makedirs(dst, exist_ok=True)
    with open(os.path.join(dst, f'{cid}.json'), 'w') as f: json.dump(draft, f, indent=2)
    os.remove(src)
    return {'ok': True, 'archived': dst}


def list_drafts():
    out = []
    for fn in sorted(os.listdir(DRAFTS)):
        if fn.endswith('.json'):
            with open(os.path.join(DRAFTS, fn)) as f:
                d = json.load(f)
                d['file'] = fn
                out.append(d)
    return out


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'help'
    if cmd == 'profiles': print(json.dumps(list_profiles(), indent=2, default=str))
    elif cmd == 'contacts': print(json.dumps(list_contacts(), indent=2, default=str)[:1500])
    elif cmd == 'segments': print(json.dumps(list_segments(), indent=2, default=str))
    elif cmd == 'drafts':   print(json.dumps(list_drafts(), indent=2, default=str))
    elif cmd == 'upsert':
        if len(sys.argv) < 3: print('usage: reach.py upsert <email> [name]'); sys.exit(2)
        name = sys.argv[3] if len(sys.argv) > 3 else ''
        parts = name.split(' ', 1)
        attrs = {}
        if len(parts) >= 1: attrs['first_name'] = parts[0]
        if len(parts) >= 2: attrs['last_name'] = parts[1]
        print(json.dumps(upsert_contact(sys.argv[2], attrs), indent=2, default=str))
    else:
        print('commands: profiles | contacts | segments | drafts | upsert <email> [name]')
