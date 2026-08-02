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
import embedding_scoring as embedding_scoring

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
# Was written but never called anywhere — self._kappa() (do_GET) referenced a
# method that didn't exist, and this free function it should have wrapped
# just sat here unused. That gap is exactly why GET /train/kappa crashed on
# every request. _kappa() below wraps this rather than duplicating the math;
# verified against sklearn.metrics.cohen_kappa_score on synthetic paired data
# (exact match to 4 decimal places, cross-checked before this was wired up).
def kappa(pairs):
    n = len(pairs)
    if n == 0: return None, 0, None, None
    cats = sorted({a for a, _ in pairs} | {b for _, b in pairs})
    agree = sum(1 for a, b in pairs if a == b)
    po = agree / n
    ca = {c: sum(1 for a, _ in pairs if a == c) / n for c in cats}
    cb = {c: sum(1 for _, b in pairs if b == c) / n for c in cats}
    pe = sum(ca[c] * cb[c] for c in cats)
    k = None if pe >= 1 else (po - pe) / (1 - pe)
    return k, n, po, pe

RUBRIC_LEVELS = ['0-missing', '1-vague', '2-specific', '3-falsifiable']

def _resolve_rater(email):
    """Map an authenticated email to 'A' | 'B' | None via CORDIA_RATER_A/B.
    Never accept rater identity from request input — see _rate()."""
    if not email:
        return None
    email = email.strip().lower()
    if email == os.environ.get('CORDIA_RATER_A', '').strip().lower() and email:
        return 'A'
    if email == os.environ.get('CORDIA_RATER_B', '').strip().lower() and email:
        return 'B'
    return None

def _rateable_candidates(course_id='aie1'):
    """The exact set of answers the real scorer would evaluate: the latest
    non-empty value per (learner, block), across every learner who has ever
    answered this course. This is deliberately the SAME collapse rule
    cordaie_scoring._latest_by_block applies per-learner, just run across all
    learners at once — raters must see what the scorer sees, or kappa
    validates a different pipeline than the one that issues certificates."""
    rows = [r for r in read_all(CORPUS) if r.get('track') == course_id and r.get('block')]
    latest = {}
    for r in sorted(rows, key=lambda r: r.get('ts', 0)):
        latest[(r.get('learner') or 'anon', r.get('block'))] = r
    return [r for r in latest.values() if (r.get('value') or '').strip()]

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
        elif p == '/train/rate/queue':
            self._rate_queue()
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
        elif p == '/pay/my-access':
            self._my_access()
        elif p == '/train/manifest':
            self._manifest()
        else:
            self._json({'error': 'not found'}, 404)

    def _kappa(self):
        """Cohen's kappa between rater A and rater B over paired /train/rate
        ratings of the same response_id.

        This is the validation gate the authoring standard requires before any
        free-text rubric ships (A8: two independent raters score >=100
        responses; kappa >= 0.80 or the rubric is rewritten). The endpoint
        previously called a method that did not exist and crashed on every
        request; this replaces it with a real computation.
        """
        ratings = read_all(RATINGS)
        # last rating per (response_id, rater) wins, same collapse rule the
        # scorers use for corpus rows
        latest = {}
        for r in ratings:
            rid, rater = r.get('response_id'), r.get('rater')
            if not (rid and rater in ('A', 'B')):
                continue
            key = (rid, rater)
            if key not in latest or r.get('ts', 0) >= latest[key].get('ts', 0):
                latest[key] = r

        by_id = {}
        for (rid, rater), r in latest.items():
            by_id.setdefault(rid, {})[rater] = r.get('level')
        pairs = [(rid, v['A'], v['B']) for rid, v in by_id.items()
                 if 'A' in v and 'B' in v]

        pool = len(_rateable_candidates())
        n = len(pairs)
        if n == 0:
            self._json({'ok': True, 'n_pairs': 0, 'candidate_pool_size': pool,
                        'kappa': None, 'passed': None, 'threshold': 0.80,
                        'note': 'No response has been rated by both A and B yet. '
                                'Kappa is undefined until paired ratings exist.'})
            return

        k_val, _, p_o, p_e = kappa([(a, b) for _, a, b in pairs])
        note = 'Expected agreement is 1.0 (no variance in ratings); kappa is undefined.' \
               if k_val is None else None

        # confusion matrix + per-block breakdown: diagnostic only, not part
        # of the pass/fail gate (that's the shared kappa() call above)
        levels = RUBRIC_LEVELS
        idx = {lvl: i for i, lvl in enumerate(levels)}
        kk = len(levels)
        confusion = [[0] * kk for _ in range(kk)]
        for _, a, b in pairs:
            if a in idx and b in idx:
                confusion[idx[a]][idx[b]] += 1

        corpus_by_id = {r.get('id'): r for r in read_all(CORPUS) if r.get('id')}
        per_block = {}
        for rid, a, b in pairs:
            block = (corpus_by_id.get(rid) or {}).get('block', 'unknown')
            d = per_block.setdefault(block, {'n': 0, 'agree': 0})
            d['n'] += 1
            d['agree'] += int(a == b)

        self._json({
            'ok': True,
            'n_pairs': n,
            'n_required': 100,
            'candidate_pool_size': pool,
            'observed_agreement': round(p_o, 4),
            'expected_agreement': round(p_e, 4),
            'kappa': round(k_val, 4) if k_val is not None else None,
            'threshold': 0.80,
            'passed': (k_val is not None and k_val >= 0.80) if n >= 100 else None,
            'note': note or (None if n >= 100 else
                     f'{n}/100 required paired ratings collected (pool currently supports '
                     f'up to {pool}) — kappa is informative but not yet a pass/fail signal '
                     'per the authoring standard.'),
            'confusion_matrix': {'levels': levels, 'matrix': confusion},
            'per_block': {b: {'n': d['n'], 'agreement': round(d['agree'] / d['n'], 3)}
                         for b, d in sorted(per_block.items())},
        })

    def _rate_queue(self):
        """This rater's next items to grade: real submitted answers this
        rater hasn't scored yet, learner identity stripped (raters shouldn't
        know whose answer they're reading). Items already rated by the OTHER
        rater are surfaced first, so pairs complete before new ground gets
        opened — the kappa gate only cares about pairs, not raw rating count."""
        token = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
        me = auth.whoami(token) if token else None
        if not me:
            self._json({'error': 'sign in required'}, 401); return
        rater = _resolve_rater(me['email'])
        if not rater:
            self._json({'error': 'this account is not on the rater list'}, 403); return
        other = 'B' if rater == 'A' else 'A'

        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        limit = min(max(int(q.get('limit', ['30'])[0] or 30), 1), 100)

        # last rating per (response_id, rater) wins — same rule _kappa() uses
        latest = {}
        for r in read_all(RATINGS):
            rid, rr = r.get('response_id'), r.get('rater')
            if not (rid and rr in ('A', 'B')):
                continue
            key = (rid, rr)
            if key not in latest or r.get('ts', 0) >= latest[key].get('ts', 0):
                latest[key] = r
        rated_by_me = {rid for (rid, rr) in latest if rr == rater}
        rated_by_other = {rid for (rid, rr) in latest if rr == other}

        pool = _rateable_candidates()
        remaining = [r for r in pool if r['id'] not in rated_by_me]
        # items the other rater already scored float to the front, so this
        # pair completes instead of both raters independently expanding
        # coverage in different directions
        remaining.sort(key=lambda r: r['id'] not in rated_by_other)

        items = [{'response_id': r['id'], 'block': r.get('block'), 'value': r.get('value'),
                  'paired': r['id'] in rated_by_other}
                 for r in remaining[:limit]]

        self._json({
            'ok': True,
            'rater': rater,
            'levels': RUBRIC_LEVELS,
            'candidate_pool_size': len(pool),
            'rated_by_me': len(rated_by_me),
            'remaining_for_me': len(remaining),
            'items': items,
        })

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
        # MUST pass the learner. Without it this reads every learner's rows for
        # the course, and the scorers' last-write-wins collapse by block scores
        # one person's certificate from whoever answered that block most recently.
        rows = _course_rows(course_id, me['email'])
        if not rows:
            self._json({'error': 'no responses found for this course'}, 400); return
        
        # The rubric scorer decides the certificate. The embedding scorer is
        # recorded alongside it as a research signal but does NOT gate anyone.
        #
        # Why: the rubric has 5-10 anchors and 3-5 negative signals for all
        # 12 blocks, and separates real submissions cleanly (33% vs 92% on two
        # live learners). The embedding scorer has 2 exemplars per block and
        # compressed those same two submissions into 73.3 vs 77.7 — a 4.4 point
        # spread — while its pass line sits at 80, so it could never certify
        # anyone. Restore it as primary only once the exemplar library is large
        # enough to discriminate, and validated against human grades.
        report = scoring.score_course(course_id, rows)
        report['scoring_method'] = 'rubric'
        try:
            shadow = embedding_scoring.score_course(course_id, rows)
            report['embedding_shadow'] = {
                'score': shadow.get('score'),
                'percent': shadow.get('percent'),
                'passed': shadow.get('passed'),
                'confidence': shadow.get('confidence'),
            }
        except Exception as e:
            print(f'embedding shadow scoring failed (non-fatal): {e}', file=sys.stderr)
            report['embedding_shadow'] = None

        cert_obj = {
            'email': me['email'],
            'name': me['name'],
            'course_id': course_id,
            'ts': time.time(),
            **report,
        }
        _save_cert(cert_obj)
        # 'score' is NOT comparable across scorers: the keyword scorer returns
        # raw points (max 3 per block, so 36 total) while the embedding scorer
        # returns 0-100. Gating on `score >= 80` therefore could never fire on
        # the keyword path. Both scorers compute `passed` correctly against
        # their own scale, and both report `percent` — use those.
        pct = float(report.get('percent', report.get('score', 0)) or 0)
        _fire_event(me['email'], 'exam_finished',
                    {'score': float(report.get('score', 0)), 'percent': pct,
                     'course_id': course_id})
        if bool(report.get('passed')):
            _fire_event(me['email'], 'exam_passed',
                        {'score': float(report.get('score', 0)), 'percent': pct,
                         'cert_url': f'https://cordiacode.com/cert/{cert_obj["email"]}',
                         'course_id': course_id})
        self._json({'ok': True, **cert_obj})

    def do_POST(self):
        p = self.path.split('?')[0]
        try:
            body = self._body()
        except Exception as e:
            self._json({'error': str(e)}, 400); return
        if p == '/train/respond':
            self._respond(body)
        elif p == '/train/survey':
            self._survey(body)
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
        elif p == '/pay/reach-webhook':
            self._reach_webhook(body)
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

    def _reach_webhook(self, body):
        try:
            import cordia_paywall as pw
        except Exception as e:
            self._json({'ok': False, 'msg': f'paywall unavailable: {e}'}, 503); return
        ok, msg = pw.handle_reach_webhook(self.headers, body)
        if ok:
            email = str(body.get('email', '')).strip().lower()
            sku   = str(body.get('sku', '')).strip()
            order = str(body.get('order_id', '')).strip()
            track = str(body.get('track', '')).strip()  # if paywall enriched it
            _fire_event(email, 'purchase',
                        {'sku': sku, 'order_id': order, 'track': track,
                         'paid_tracks': [track] if track else None})
        self._json({'ok': ok, 'msg': msg}, 200 if ok else 403)

    def _my_access(self):
        token = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
        me = auth.whoami(token) if token else None
        if not me:
            self._json({'ok': False, 'msg': 'sign in required'}, 401); return
        try:
            import cordia_paywall as pw
        except Exception as e:
            self._json({'ok': False, 'msg': f'paywall unavailable: {e}'}, 503); return
        self._json({'ok': True, 'email': me['email'],
                    'free_tracks': sorted(pw.FREE_TRACKS),
                    'entitlements': pw.my_entitlements(me['email'])})

    def _manifest(self):
        token = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
        me = auth.whoami(token) if token else None
        if not me:
            self._json({'ok': False, 'msg': 'sign in required'}, 401); return
        try:
            from sixs.profile_compiler import compile_profile
            from sixs.agent_manifest import build_manifest
        except Exception as e:
            self._json({'ok': False, 'msg': f'manifest unavailable: {e}'}, 503); return
        import urllib.parse as up
        q = up.parse_qs(up.urlparse(self.path).query)
        industries = [i for i in q.get('industries', [''])[0].split(',') if i]
        profile = compile_profile(me['email'])
        if not profile:
            self._json({'ok': False, 'msg': 'no score data yet — take the exam first'}, 404); return
        # survey gate: the assessment is "paid for" with the exit survey
        done = any(r.get('kind') == 'aie1-exit-survey' and r.get('learner') == me['email']
                   for r in read_all(CORPUS))
        if not done:
            self._json({'ok': False, 'survey_required': True,
                        'msg': 'complete the 90-second exit survey to unlock your assessment'}, 402); return
        self._json({'ok': True, 'profile': profile,
                    'manifest': build_manifest(profile, industries)})

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
        if learner and '@' in learner and block:
            _fire_event(learner, 'exam_started' if block in ('C1','C2') else 'block_submitted',
                        {'track': track, 'block': block})
        self._json({'ok': True, 'id': rec['id']})

    def _survey(self, body):
        token = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
        me = auth.whoami(token) if token else None
        if not me:
            self._json({'ok': False, 'msg': 'sign in required'}, 401); return
        answers = body.get('answers')
        if not isinstance(answers, dict):
            self._json({'ok': False, 'msg': 'answers required'}, 400); return
        required = ['intent_clarity', 'interpretation_gap', 'effort_source', 'confidence', 'role']
        missing = [k for k in required if answers.get(k) is None]
        if missing:
            self._json({'ok': False, 'msg': 'missing: ' + ', '.join(missing)}, 400); return
        rec = {
            'id': uuid.uuid4().hex[:12],
            'kind': 'aie1-exit-survey',
            'learner': me['email'],
            'ts': time.time(),
            'answers': {k: answers.get(k) for k in required + ['transfer']},
        }
        append(CORPUS, rec)
        self._json({'ok': True, 'id': rec['id']})

    def _rate(self, body):
        # Rater identity is resolved server-side from the authenticated
        # session and CORDIA_RATER_A/B — never trusted from the request body.
        # It used to accept an arbitrary 'rater':'A'|'B' from the client with
        # no auth at all, meaning anyone could post as either rater and
        # invalidate the entire kappa study. The whole point of this endpoint
        # is independent human judgment; that only holds if identity is real.
        token = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
        me = auth.whoami(token) if token else None
        if not me:
            self._json({'error': 'sign in required'}, 401); return
        rater = _resolve_rater(me['email'])
        if not rater:
            self._json({'error': 'this account is not on the rater list'}, 403); return

        resp_id = re.sub(r'[^a-f0-9]', '', str(body.get('response_id', '')))[:16]
        level = body.get('level') if body.get('level') in RUBRIC_LEVELS else None
        if not (resp_id and level):
            self._json({'error': 'response_id, level required'}, 400); return
        append(RATINGS, {'response_id': resp_id, 'rater': rater, 'level': level,
                         'ts': time.time()})
        self._json({'ok': True, 'rater': rater})

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


def _fire_event(email, kind, meta=None):
    """Best-effort fire-and-forget to cordia-pipeline. Never blocks the request."""
    try:
        import urllib.request, json as _json
        body = _json.dumps({'email': email, 'kind': kind, 'meta': meta or {}}).encode()
        req = urllib.request.Request('http://127.0.0.1:9997/pipeline/track',
                                      data=body, method='POST', headers={
                                          'Content-Type': 'application/json',
                                          'User-Agent': 'cordia-training/1.0',
                                      })
        urllib.request.urlopen(req, timeout=2).read()
    except Exception:
        pass


import urllib.parse
if __name__ == '__main__':
    print(f'cordia-training backend on :{PORT}')
    HTTPServer(('0.0.0.0', PORT), H).serve_forever()
