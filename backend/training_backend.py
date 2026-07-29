#!/usr/bin/env python3
"""Cordia Training backend — response ingest, corpus store, rater scoring + Cohen's kappa,
LLM proxy for live Archetype C environments. Port 9995.
Stdlib only. Storage: /var/lib/cordia/corpus/corpus.jsonl (append-only)."""

import json, os, re, time, threading, urllib.request, uuid, sys
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, '/opt/cordia/backend')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # dev/local runs
import cordia_auth as auth
import cordaie_scoring as scoring

# 6S shadow scoring — passive observer, never authoritative.
# cordaie_scoring above stays the only source of learner-visible numbers. If
# the sixs package is absent, psycopg2 is missing, or no DSN is configured,
# this import fails softly and the exam behaves exactly as it did before.
try:
    from sixs import shadow as sixs_shadow
except BaseException as _sixs_err:            # noqa: BLE001 - must never be fatal
    sixs_shadow = None
    print(f'6S shadow scoring unavailable ({type(_sixs_err).__name__}: {_sixs_err}); '
          f'exam unaffected', file=sys.stderr)

PORT = 9995
DATA = '/var/lib/cordia/corpus'
CORPUS = os.path.join(DATA, 'corpus.jsonl')
RATINGS = os.path.join(DATA, 'ratings.jsonl')
CERTS = os.path.join(DATA, 'certifications.jsonl')
os.makedirs(DATA, exist_ok=True)
lock = threading.RLock()

# course registry kept server-side so future courses can extend cleanly
COURSES = {'aie1': 'CordiaAIE-1'}

def _course_rows(course_id, learner=None):
    rows = read_all(CORPUS)
    rows = [r for r in rows if r.get('track') == course_id]
    if learner:
        rows = [r for r in rows if r.get('learner') == learner]
    return rows


def _course_summary(course_id, learner):
    rows = _course_rows(course_id, learner)
    if not rows:
        return None
    return scoring.score_course(course_id, rows)

def _save_cert(obj):
    append(CERTS, obj)

def _latest_cert(email, course_id):
    rows = read_all(CERTS)
    for r in reversed(rows):
        if r.get('email') == email and r.get('course_id') == course_id:
            return r
    return None

# --- rate limiting (dual-key: per-IP AND per-email, per Claude review) ---
WINDOW = 600          # 10 min
IP_CAP = 10           # auth attempts per IP per window
EMAIL_CAP = 5         # auth attempts per target email per window
LLM_CAP = 30          # llm calls per user per window (paid upstream)
_rl = {'ip': {}, 'email': {}, 'llm': {}}

def _hit(bucket, key, cap):
    now = time.time()
    dq = bucket.setdefault(key, deque())
    while dq and dq[0] < now - WINDOW:
        dq.popleft()
    if len(dq) >= cap:
        return False
    dq.append(now)
    if not dq:
        bucket.pop(key, None)
    return True

def rate_ok(ip, email=None, llm=False):
    with lock:
        if llm:
            return _hit(_rl['llm'], (email or '').strip().lower() or ip, LLM_CAP)
        if not _hit(_rl['ip'], ip, IP_CAP):
            return False
        if email and not _hit(_rl['email'], email.strip().lower(), EMAIL_CAP):
            return False
        return True

NOUS_URL = 'https://inference-api.nousresearch.com/v1/chat/completions'
NOUS_MODEL = 'moonshotai/kimi-k3'

def nous_key():
    d = json.load(open('/root/.hermes/auth.json'))
    return d['providers']['nous']['agent_key']

def append(path, obj):
    with lock:
        with open(path, 'a') as f:
            f.write(json.dumps(obj) + '\n')

def read_all(path):
    if not os.path.exists(path): return []
    with lock:
        with open(path) as f:
            return [json.loads(l) for l in f if l.strip()]

# --- Cohen's kappa (weighted not needed; nominal categories) ---
def kappa(pairs):
    n = len(pairs)
    if n == 0: return None, 0, None
    cats = sorted({a for a, _ in pairs} | {b for _, b in pairs})
    agree = sum(1 for a, b in pairs if a == b)
    po = agree / n
    ca = {c: sum(1 for a, _ in pairs if a == c) / n for c in cats}
    cb = {c: sum(1 for _, b in pairs if b == c) / n for c in cats}
    pe = sum(ca[c] * cb[c] for c in cats)
    k = None if pe >= 1 else (po - pe) / (1 - pe)
    return k, n, po

RUBRIC_LEVELS = ['0-missing', '1-vague', '2-specific', '3-falsifiable']

def call_llm(system, user, max_tokens=900):
    body = json.dumps({
        'model': NOUS_MODEL,
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
        'max_tokens': max_tokens, 'temperature': 0.4
    }).encode()
    req = urllib.request.Request(NOUS_URL, data=body, headers={
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + nous_key()
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read())
    return d['choices'][0]['message']['content']

class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self._cors()
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def _body(self):
        n = int(self.headers.get('Content-Length', 0))
        if n > 2_000_000: raise ValueError('body too large')
        return json.loads(self.rfile.read(n) or b'{}')

    def log_message(self, *a): pass

    def do_GET(self):
        p = self.path.split('?')[0]
        if p == '/train/status':
            self._json({'ok': True, 'service': 'cordia-training', 'responses': len(read_all(CORPUS)),
                        'ratings': len(read_all(RATINGS)), 'ts': time.time()})
        elif p == '/train/responses':
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            track = q.get('track', [None])[0]
            rows = read_all(CORPUS)
            if track: rows = [r for r in rows if r.get('track') == track]
            token = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
            authed = bool(auth.whoami(token)) if token else False
            if not authed:
                rows = [{k: v for k, v in r.items() if k != 'learner'} for r in rows]
            self._json({'responses': rows[-500:]})
        elif p == '/train/kappa':
            self._kappa()
        elif p == '/auth/me':
            token = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
            me = auth.whoami(token)
            self._json({'ok': bool(me), 'user': me}, 200 if me else 401)
        elif p == '/train/research':
            self._research()
        elif p == '/train/certification':
            self._certification()
        elif p == '/train/6s/status':
            self._sixs_status()
        elif p == '/train/6s/scores':
            self._sixs_scores()
        else:
            self._json({'error': 'not found'}, 404)

    def _research(self):
        token = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
        if not (token and auth.whoami(token)):
            self._json({'error': 'sign in required'}, 401); return
        rows = read_all(CORPUS)
        ratings = read_all(RATINGS)
        rmap = {}
        for r in ratings:
            rmap.setdefault(r['response_id'], {})[r['rater']] = r['level']
        rows_sorted = sorted(rows, key=lambda r: r.get('ts', 0))
        seq = {}
        out = []
        for r in rows_sorted:
            learner = r.get('learner', 'anon')
            seq[learner] = seq.get(learner, 0) + 1
            v = r.get('value', '')
            words = v.split()
            out.append({
                'id': r.get('id'), 'track': r.get('track'), 'block': r.get('block'),
                'learner': learner, 'ts': r.get('ts'),
                'learner_seq': seq[learner],
                'n_words': len(words), 'n_chars': len(v),
                'n_questions': v.count('?'),
                'has_numbers': any(ch.isdigit() for ch in v),
                'rated_levels': rmap.get(r.get('id'), {}),
            })
        pairs = []
        by_lt = {}
        for r in rows_sorted:
            key = (r.get('learner'), r.get('track'))
            by_lt.setdefault(key, {})[r.get('block')] = r
        for (learner, track), blocks in by_lt.items():
            if 'C1' in blocks and 'C2' in blocks:
                pairs.append({'learner': learner, 'track': track,
                              'v1_words': len(blocks['C1'].get('value','').split()),
                              'v2_words': len(blocks['C2'].get('value','').split()),
                              'v1_ts': blocks['C1'].get('ts'), 'v2_ts': blocks['C2'].get('ts')})
        self._json({'n_rows': len(out), 'rows': out, 'revision_pairs': pairs,
                    'note': 'features for articulation-gap ML; import into pandas directly'})

    def _certification(self):
        token = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
        me = auth.whoami(token) if token else None
        if not me:
            self._json({'error': 'sign in required'}, 401); return
        course_id = 'aie1'
        cert = _latest_cert(me['email'], course_id)
        if cert:
            self._json({'ok': True, 'cached': True, **cert})
            return
        rows = _course_rows(course_id)
        if not rows:
            self._json({'error': 'no responses found for this course'}, 400); return
        report = scoring.score_course(course_id, rows)
        cert_obj = {
            'email': me['email'],
            'name': me['name'],
            'course_id': course_id,
            'ts': time.time(),
            **report,
        }
        _save_cert(cert_obj)
        self._json({'ok': True, **cert_obj})

    def do_POST(self):
        p = self.path.split('?')[0]
        try:
            body = self._body()
        except Exception as e:
            self._json({'error': str(e)}, 400); return
        if p == '/train/respond':
            self._respond(body)
        elif p == '/train/rate':
            self._rate(body)
        elif p == '/train/llm':
            self._llm(body)
        elif p == '/auth/signup':
            self._auth_2fa(auth.signup, body)
        elif p == '/auth/verify-signup':
            self._auth_verify(auth.verify_signup, body)
        elif p == '/auth/login':
            self._auth_2fa(auth.login, body)
        elif p == '/auth/verify-login':
            self._auth_verify(auth.verify_login, body)
        elif p == '/auth/logout':
            auth.logout(str(body.get('token', '')))
            self._json({'ok': True})
        elif p == '/auth/enroll':
            self._enroll()
        else:
            self._json({'error': 'not found'}, 404)

    def _client_ip(self):
        if self.client_address[0] == '127.0.0.1':
            xff = self.headers.get('X-Forwarded-For', '').split(',')
            xff = [x.strip() for x in xff if x.strip()]
            if xff: return xff[-1]
        return self.client_address[0]

    def _auth_2fa(self, fn, body):
        ip = self._client_ip()
        email = str(body.get('email', ''))[:200]
        if not rate_ok(ip, email.lower() or None):
            self._json({'ok': False, 'msg': 'too many attempts — wait 10 minutes and try again'}, 429)
            return
        name = str(body.get('name', ''))[:120]
        pw = str(body.get('password', ''))[:200]
        args = (email, name, pw) if fn is auth.signup else (email, pw)
        ok, msg, dev_code = fn(*args)
        out = {'ok': ok, 'msg': msg}
        if dev_code: out['dev_code'] = dev_code
        self._json(out, 200 if ok else 400)

    def _auth_verify(self, fn, body):
        ip = self._client_ip()
        email = str(body.get('email', ''))[:200]
        if not rate_ok(ip, email.lower() or None):
            self._json({'ok': False, 'msg': 'too many attempts — wait 10 minutes and try again'}, 429)
            return
        code = str(body.get('code', ''))[:12]
        ok, msg, token = fn(email, code)
        out = {'ok': ok, 'msg': msg}
        if token: out['token'] = token
        self._json(out, 200 if ok else 400)

    def _enroll(self):
        ip = self._client_ip()
        if not rate_ok(ip, None):
            self._json({'ok': False, 'msg': 'too many attempts'}, 429); return
        token = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
        try:
            import cordia_enroll as enr
        except Exception as e:
            self._json({'ok': False, 'msg': f'enrollment unavailable: {e}'}, 503); return
        result, err = None, None
        try:
            result, err = enr.enroll(token)
        except Exception as e:
            self._json({'ok': False, 'msg': f'enrollment failed: {e}'}, 503); return
        if err:
            self._json({'ok': False, 'msg': err}, 401 if 'sign in' in err else 403); return
        self._json({'ok': True, **result})

    def _sixs_status(self):
        """Read-only health of the 6S shadow scorer.

        Deliberately a NEW endpoint rather than extra keys on /train/status:
        the ops TUI deserialises that response, and leaving it byte-identical
        means ops cannot be affected by this feature at all.
        """
        if sixs_shadow is None:
            self._json({'ok': False, 'available': False,
                        'reason': 'sixs package not importable',
                        'shadow_mode': True, 'learner_visible': False})
            return
        try:
            out = sixs_shadow.status()
            out['tables'] = sixs_shadow.table_counts()
            self._json({'ok': True, 'available': True, **out})
        except BaseException as e:            # noqa: BLE001
            self._json({'ok': False, 'available': True,
                        'error': f'{type(e).__name__}: {e}'[:200]})

    def _sixs_scores(self):
        """Read back recorded 6S matrices. Requires a signed-in session.

        Inspection endpoint, not a result endpoint. The learner's actual
        certification outcome still comes from /train/certification via
        cordaie_scoring. These numbers are unvalidated (see sixs/rubric.py) and
        the response says so on every payload.

        A signed-in user sees only their own rows. Reading everyone's rows
        requires being listed in CORDIA_6S_ADMIN (comma-separated emails).
        """
        token = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
        me = auth.whoami(token) if token else None
        if not me:
            self._json({'ok': False, 'msg': 'sign in required'}, 401); return
        if sixs_shadow is None:
            self._json({'ok': False, 'available': False,
                        'reason': 'sixs package not importable'}); return
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        try:
            limit = int(q.get('limit', ['50'])[0])
        except (ValueError, TypeError):
            limit = 50
        admins = {e.strip().lower() for e in
                  os.environ.get('CORDIA_6S_ADMIN', '').split(',') if e.strip()}
        is_admin = str(me.get('email', '')).lower() in admins
        learner = q.get('learner', [None])[0] if is_admin else me.get('email')
        out = sixs_shadow.recent_scores(limit=limit, learner=learner)
        self._json({'ok': 'error' not in out,
                    'shadow_mode': True, 'learner_visible': False,
                    'note': 'unvalidated heuristic scores — not a certification result',
                    'scope': learner or 'all', 'admin': is_admin, **out})

    def _respond(self, body):
        track = re.sub(r'[^a-z0-9-]', '', str(body.get('track', '')))[:40]
        block = re.sub(r'[^A-Za-z0-9]', '', str(body.get('block', '')))[:8]
        value = str(body.get('value', ''))[:50000]
        learner = re.sub(r'[^a-zA-Z0-9@._-]', '', str(body.get('learner', 'anon')))[:80]
        token = str(body.get('token', ''))
        if token:
            me = auth.whoami(token)
            if me: learner = me['email']
        if not track or not block or not value.strip():
            self._json({'error': 'track, block, value required'}, 400); return
        rec = {'id': uuid.uuid4().hex[:12], 'track': track, 'block': block,
               'value': value, 'learner': learner, 'ts': time.time()}
        append(CORPUS, rec)
        # Shadow-score in the background. submit() only enqueues and returns —
        # it does no scoring, no I/O and no database work on this thread, and
        # swallows everything, so the learner response below is unaffected in
        # both latency and outcome.
        if sixs_shadow is not None:
            sixs_shadow.submit(rec, lambda: _course_rows(track, learner))
        self._json({'ok': True, 'id': rec['id']})

    def _rate(self, body):
        resp_id = re.sub(r'[^a-f0-9]', '', str(body.get('response_id', '')))[:16]
        rater = body.get('rater') if body.get('rater') in ('A', 'B') else None
        level = body.get('level') if body.get('level') in RUBRIC_LEVELS else None
        if not (resp_id and rater and level):
            self._json({'error': 'response_id, rater (A|B), level required'}, 400); return
        append(RATINGS, {'response_id': resp_id, 'rater': rater, 'level': level, 'ts': time.time()})
        self._json({'ok': True})

    def _llm(self, body):
        envs = {
            'software': "You are playing the role of an AI coding assistant inside a training environment. Scenario: a nightly script syncs inventory from a supplier CSV into a database; it silently truncates the import at any row with a blank SKU. Respond to the learner's instruction AS the assistant would — produce a plan or result. Stay in scenario.",
            'trades': "You are an AI field-assistant on a phone. Scenario: an electrical panel, a breaker trips about an hour after reset, only in the afternoon. Respond to the learner's description with a diagnostic suggestion. Stay in scenario.",
            'healthcare': "You are a clinical documentation assistant. Scenario: synthetic patient record — pneumonia diagnosis, but the med list includes warfarin for AFib (the contradiction). Respond to the learner's drafting request. Stay in scenario.",
            'finance': "You are an AI accounting assistant. Scenario: month-end close with three variances — office supplies +$212 (immaterial), contractor spend +$41,300, revenue accrual timing off $118,000. Respond to the learner's instruction. Stay in scenario.",
            'legal': "You are an AI contract-review assistant. Scenario: a 14-page vendor agreement, mostly boilerplate, but section 11.3 has a non-standard indemnity clause (gross-negligence-only carve-out, 3-month fee cap). Respond to the learner. Stay in scenario.",
            'engineering': "You are an AI engineering analysis assistant. Scenario: tolerance stack-up — shaft 25.00 +0/-0.021mm, bore 25.00 +0.033/-0mm; parts assembled at -20C, aluminum housing, steel shaft. Respond to the learner. Stay in scenario.",
            'construction': "You are an AI construction scheduling assistant. Scenario: owner wants a 2-week compression; proposed sequence pour-frame-roughin-drywall ignores inspection gates and cure time. Respond to the learner. Stay in scenario.",
            'marketing': "You are an AI copywriting assistant. Scenario: probiotic supplement campaign, warm confident science-adjacent voice; legal constraint — no unsubstantiated superiority or outcome claims. Respond to the learner's brief. Stay in scenario.",
            'sales': "You are an AI sales assistant drafting follow-ups. Scenario: CRM has company/contact/product only; the real relationship state (bad demo, quiet champion, price pushback) is NOT in the CRM. Respond to the learner. Stay in scenario.",
            'supplychain': "You are an AI supply-chain optimization assistant. Scenario: proposal to cut safety stock 40% on a top SKU feeding 3 regional DCs, one serving an SLA customer with penalty clauses. Respond to the learner. Stay in scenario.",
            'hr': "You are an AI resume-screening assistant. Scenario: 400 applications screened on 'leadership signals'; pass-through rate for women is 42% of men's. Respond to the learner. Stay in scenario.",
            'education': "You are an AI tutoring-content assistant. Scenario: a student's algebra work shows inconsistent sign-changes when transposing, worse on subtraction. Respond to the learner's request. Stay in scenario.",
            'energy': "You are an AI sustainability-reporting assistant. Scenario: emissions calculation — agent computed Scope 1 only but labeled it 'total carbon footprint'. Respond to the learner. Stay in scenario.",
            'public': "You are an AI benefits-determination assistant. Scenario: applicant flagged for income over threshold, but it includes an excluded one-time retroactive disability payment; log shows only the flag, no reasoning. Respond to the learner. Stay in scenario.",
            'frontline': "You are an AI service assistant on a front-desk tablet. Scenario: guest whose room wasn't ready, then the restaurant lost their anniversary reservation; a line is forming. Respond to the learner's one-line instruction. Stay in scenario.",
        }
        env = body.get('env') if body.get('env') in envs else 'software'
        instruction = str(body.get('instruction', ''))[:8000]
        if not instruction.strip():
            self._json({'error': 'instruction required'}, 400); return
        token = str(body.get('token', ''))
        me = auth.whoami(token) if token else None
        if not me:
            self._json({'ok': False, 'error': 'sign in to use the live environment'}, 401); return
        if not rate_ok(self._client_ip(), me['email'], llm=True):
            self._json({'ok': False, 'error': 'environment call limit reached — wait 10 minutes'}, 429); return
        try:
            out = call_llm(envs[env], instruction)
            self._json({'ok': True, 'output': out, 'env': env})
        except Exception as e:
            self._json({'error': f'llm call failed: {e}'}, 502)

import urllib.parse
if __name__ == '__main__':
    print(f'cordia-training backend on :{PORT}')
    HTTPServer(('0.0.0.0', PORT), H).serve_forever()
