#!/usr/bin/env python3
"""Cordia Training backend — response ingest, corpus store, rater scoring + Cohen's kappa,
LLM proxy for live Archetype C environments. Port 9995.
Stdlib only. Storage: /var/lib/cordia/corpus/corpus.jsonl (append-only)."""

import json, os, re, time, threading, urllib.request, uuid, sys
from collections import deque
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, '/opt/cordia/backend')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # dev/local runs
import cordia_auth as auth
import cordaie_scoring as scoring
from runtime_paths import corpus_directory

# Embedding scoring is a research-only shadow signal. It must never keep the
# authenticated product, Surveyor, or live workspace from starting when its
# optional heavyweight runtime is unavailable.
try:
    import embedding_scoring
except BaseException as _embedding_err:       # noqa: BLE001 - intentionally non-fatal
    embedding_scoring = None
    print(f'embedding shadow scoring unavailable ({type(_embedding_err).__name__}: {_embedding_err}); '
          f'certification remains rubric-scored', file=sys.stderr)

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

# Surveyor — conversational intake, profile, and the agentic interface builder.
# Imported softly for the same reason as sixs above: if psycopg2, the DSN or the
# package itself is missing, the exam and auth must keep working untouched. The
# /surveyor/* routes then answer 503 rather than the process failing to boot.
try:
    import surveyor
    from surveyor import preflight as surveyor_preflight
    surveyor.store.init_schema()
except BaseException as _surv_err:            # noqa: BLE001 - must never be fatal
    surveyor = None
    print(f'Surveyor unavailable ({type(_surv_err).__name__}: {_surv_err}); '
          f'exam and auth unaffected', file=sys.stderr)

PORT = 9995


# Bind address. Defaults to loopback: these services have no authentication on
# any route, and were previously bound to 0.0.0.0 AND proxied publicly, which
# let anyone on the internet read the inter-agent message bus and POST a message
# addressed to 'engineer' — whose poller feeds message text into `claude -p`
# with --allowedTools Read,Write,Edit,Bash. Unauthenticated prompt injection
# into an agent with shell access on this box.
#
# Everything that legitimately talks to these runs on this host and already uses
# 127.0.0.1 (see cordia-engineer.service). Override only with a specific private
# address; never 0.0.0.0.
BIND = os.environ.get('CORDIA_BIND', '127.0.0.1')

# Production cookies must stay HTTPS-only. Localhost preview uses plain HTTP,
# so it can explicitly opt out through CORDIA_COOKIE_SECURE=0 without changing
# the safe production default.

# How many corpus rows an unauthenticated caller may read. Enough to inspect the
# shape of the data, far short of a bulk export of everyone's answers.
ANON_SAMPLE = 25

# CORS was 'Access-Control-Allow-Origin: *' on every route including the
# authenticated ones. Not directly exploitable — tokens live in localStorage
# rather than cookies, so a hostile page has nothing to replay — but there is no
# reason for any origin to be able to read these responses. In production the
# browser and the API are same-origin behind Apache; only local development is
# genuinely cross-origin.
ALLOWED_ORIGINS = {
    'https://cordiacode.com', 'https://www.cordiacode.com',
    'http://localhost:8000', 'http://127.0.0.1:8000',
    'http://localhost:5500', 'http://127.0.0.1:5500',
}

DATA = corpus_directory()
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


def _course_blocks(course_id):
    """Every block the rubric expects for a course, in rubric order."""
    try:
        rubrics = scoring._load_rubrics()[course_id]
    except Exception:
        return []
    return [b for m in rubrics.get('modules', []) for b in m.get('questions', {})]


def _completed_course(email, course_id):
    """Has this learner actually finished the course?

    A saved certificate is the direct answer. Where there is none — the learner
    never opened their result — every rubric block having an answer is the same
    fact arrived at the long way. Both are checked because the exit survey gate
    should turn on finishing the work, not on having viewed a page.
    """
    if _latest_cert(email, course_id):
        return True
    blocks = _course_blocks(course_id)
    if not blocks:
        return False
    answered = {r.get('block') for r in _course_rows(course_id, email) if str(r.get('value', '')).strip()}
    return all(b in answered for b in blocks)


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
ADMIN_CAP = 20        # admin/agent-control attempts per IP per window
_rl = {'ip': {}, 'email': {}, 'llm': {}, 'admin': {}}

def _hit(bucket, key, cap):
    now = time.time()
    dq = bucket.setdefault(key, deque())
    while dq and dq[0] < now - WINDOW:
        dq.popleft()
    if len(dq) >= cap:
        return False
    dq.append(now)
    return True

def rate_ok(ip, email=None, llm=False, admin=False):
    if admin:
        return _hit(_rl['admin'], ip, ADMIN_CAP)
    if llm:
        return _hit(_rl['llm'], (email or '').strip().lower() or ip, LLM_CAP)
    if not _hit(_rl['ip'], ip, IP_CAP):
        return False
    if email and not _hit(_rl['email'], email.strip().lower(), EMAIL_CAP):
        return False
    return True


# LLM provider is env-driven so switching backends is a config change, not a
# code change. Defaults preserve the original Nous behavior exactly; set
# LLM_BASE_URL / LLM_MODEL / LLM_KEY in /etc/cordia/cordia.env to move to
# another OpenAI-compatible provider (e.g. NVIDIA integrate.api.nvidia.com).
def _llm_config():
    url = os.environ.get('LLM_BASE_URL') or 'https://inference-api.nousresearch.com/v1/chat/completions'
    model = os.environ.get('LLM_MODEL') or 'moonshotai/kimi-k3'
    key = os.environ.get('LLM_KEY')
    if not key:
        d = json.load(open('/root/.hermes/auth.json'))
        key = d['providers']['nous']['agent_key']
    return url, model, key

def nous_key():
    # Kept as the credential probe for the surveyor status path — returns the
    # active provider key so callers can tell configured from unconfigured.
    return _llm_config()[2]

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
    url, model, key = _llm_config()
    body = json.dumps({
        'model': model,
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
        'max_tokens': max_tokens, 'temperature': 0.4
    }).encode()
    # The User-Agent is load-bearing, not decoration. urllib sends
    # "Python-urllib/3.x" by default and the upstream WAF blocks it outright
    # with a 403 (Cloudflare 1010) before the key is ever examined — which
    # looked exactly like an auth failure. Verified: curl reaches the API fine,
    # urllib without this header does not, urllib with it does.
    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json',
        'User-Agent': 'cordia-training/1.0',
        'Authorization': 'Bearer ' + key
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read())
    return d['choices'][0]['message']['content']

class H(BaseHTTPRequestHandler):
    def _cors(self):
        origin = self.headers.get('Origin', '')
        self.send_header('Vary', 'Origin')
        if origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        # Pending session-cookie mutation rides inside the response's own
        # header block. Calling send_header() before send_response() writes
        # the cookie bytes straight to the socket BEFORE the status line —
        # protocol corruption that showed up as clients receiving
        # "Set-Cookie: ...HTTP/1.0 200 OK" as the body.
        pending = getattr(self, '_pending_cookie', None)
        if pending:
            self.send_header('Set-Cookie', pending)
            self._pending_cookie = None
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
        self.send_header('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        self._cors()
        self.end_headers()
        self.wfile.write(b)

    def _set_session_cookie(self, token):
        if not token:
            return
        secure = (surveyor.runtime_config.cookie_secure(os.environ)
                  if surveyor is not None else 'Secure; ')
        self._pending_cookie = (f'cordia_session={token}; HttpOnly; {secure}SameSite=Strict; '
                                f'Max-Age={int(os.environ.get("SESSION_TTL", 86400))}; Path=/;')

    def _clear_session_cookie(self):
        secure = (surveyor.runtime_config.cookie_secure(os.environ)
                  if surveyor is not None else 'Secure; ')
        self._pending_cookie = f'cordia_session=; HttpOnly; {secure}SameSite=Strict; Max-Age=0; Path=/'

    def _token(self):
        """Session token for this request. Cookie first, Authorization header
        second — the cookie is the canonical path (browser sends it
        automatically, JS never touches it); the header stays for CLI/API
        callers that already use it."""
        for part in (self.headers.get('Cookie', '') or '').split(';'):
            k, _, v = part.strip().partition('=')
            if k == 'cordia_session' and v:
                return v.strip()
        return self.headers.get('Authorization', '').replace('Bearer ', '').strip()

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def _body(self):
        n = int(self.headers.get('Content-Length', 0) or 0)
        if n <= 0:
            return {}
        if n > 2_000_000: raise ValueError('body too large')
        return json.loads(self.rfile.read(n) or b'{}')

    def log_message(self, *a): pass

    def do_GET(self):
        p = self.path.split('?')[0]
        if p == '/healthz':
            self._healthz()
        elif p == '/train/status':
            self._json({'ok': True, 'service': 'cordia-training', 'responses': len(read_all(CORPUS)),
                        'ratings': len(read_all(RATINGS)), 'ts': time.time()})
        elif p == '/train/responses':
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            track = q.get('track', [None])[0]
            rows = read_all(CORPUS)
            if track: rows = [r for r in rows if r.get('track') == track]
            token = self._token()
            authed = bool(auth.whoami(token)) if token else False
            if authed:
                self._json({'responses': rows[-500:], 'total': len(rows)}); return
            # Anonymous callers get a capped, de-identified sample.
            #
            # This used to hand out the entire corpus — 222 free-text answers —
            # to anyone who asked. Stripping `learner` kept it out of PII
            # territory, but it is still user-authored content published without
            # consent, and it is the one dataset Cordia's own positioning calls
            # rare and hard to copy. Giving it away wholesale was the problem,
            # not the field names.
            #
            # A sample stays useful for anyone inspecting the shape of the data
            # while ceasing to be a bulk export.
            sample = [{k: v for k, v in r.items() if k != 'learner'} for r in rows[-ANON_SAMPLE:]]
            self._json({'responses': sample, 'total': len(rows),
                        'sampled': True, 'limit': ANON_SAMPLE,
                        'note': 'sign in for the full corpus'})
        elif p == '/train/kappa':
            self._kappa()
        elif p == '/train/rate/queue':
            self._rate_queue()
        elif p == '/auth/me':
            token = self._token()
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
        elif p == '/surveyor/profile':
            self._surv_profile()
        elif p == '/surveyor/operator-profile':
            self._surv_operator_profile()
        elif p == '/account/profile':
            self._account_profile()
        elif p == '/surveyor/conversation':
            self._surv_conversation()
        elif p == '/surveyor/interfaces':
            self._surv_list_interfaces()
        elif p == '/surveyor/workspace':
            self._surv_workspace()
        elif p == '/surveyor/alidora/map':
            self._surv_alidora_map()
        elif p == '/surveyor/admin':
            self._surv_admin()
        elif p == '/surveyor/recommendation':
            self._surv_recommendation()
        elif p == '/surveyor/fde-recommendations':
            self._surv_fde_recommendations()
        elif p == '/surveyor/artifacts':
            self._surv_artifacts()
        elif p == '/surveyor/approvals':
            self._surv_approvals()
        elif p == '/surveyor/capabilities':
            self._surv_capabilities()
        elif p == '/surveyor/skills':
            self._surv_skills()
        elif p == '/surveyor/activity':
            self._surv_activity()
        elif p == '/surveyor/preflight':
            self._surv_preflight()
        elif p == '/surveyor/github/repositories':
            self._surv_github_repositories()
        elif p == '/surveyor/export':
            self._surv_export()
        elif p == '/admin/users':
            self._admin_users()
        else:
            self._json({'error': 'not found'}, 404)

    # ---------------------------------------------------------- surveyor

    def _healthz(self):
        """Public-safe process readiness; details remain behind authenticated preflight."""
        report = surveyor_preflight.report() if surveyor is not None else {'ok': False}
        self._json(surveyor_preflight.health_view(report) if surveyor is not None else {'ok': False},
                   200 if report.get('ok') else 503)

    def _surv_me(self):
        """Authenticated identity for a /surveyor/* request, or None.

        Token from the Authorization header or the JSON body, matching the two
        conventions already in use on this server (GET /auth/me reads the
        header, POST /train/llm reads the body)."""
        token = self._token()
        if not token:
            token = str(getattr(self, '_surv_body', {}).get('token', ''))
        return auth.whoami(token) if token else None

    def _surv_guard(self):
        """Returns (email, None) or (None, True) having already sent the error."""
        if surveyor is None:
            self._json({'ok': False, 'error': 'surveyor unavailable'}, 503)
            return None, True
        me = self._surv_me()
        if not me:
            self._json({'ok': False, 'error': 'sign in to use Surveyor'}, 401)
            return None, True
        return me['email'], None

    def _surv_llm(self):
        """The model callable Surveyor should use right now.

        nous_key is the probe: it raises if the credential is unreadable, which
        is currently the case in production (the file is root-only and this
        service runs as `cordia`). When that is fixed the same call starts
        returning the live caller with no other change."""
        caller, _live = surveyor.llm.caller(call_llm, probe=nous_key)
        return caller

    def _surv_profile(self):
        email, stop = self._surv_guard()
        if stop: return
        self._json({'ok': True, 'llm': surveyor.llm.status(nous_key),
                    **surveyor.pipeline.public_profile(email)})

    def _surv_operator_profile(self):
        """Read-only, least-privilege bridge from Surveyor to one workspace action."""
        email, stop = self._surv_guard()
        if stop: return
        profile = surveyor.pipeline.load_profile(email)
        connector_states = surveyor.store.get_connector_states(email)
        interfaces = surveyor.store.list_interfaces(email)
        self._json({
            'ok': True,
            'operator_profile': surveyor.operator_profile.build(
                profile, connector_states, interfaces),
        })

    def _surv_conversation(self):
        email, stop = self._surv_guard()
        if stop: return
        self._json({'ok': True, **surveyor.pipeline.start(email)})

    def _surv_message(self, body):
        email, stop = self._surv_guard()
        if stop: return
        if not rate_ok(self._client_ip(), email, llm=True):
            self._json({'ok': False, 'error': 'message limit reached — wait 10 minutes'}, 429)
            return
        out = surveyor.pipeline.turn(email, str(body.get('message', '')), self._surv_llm(),
                                     choice=body.get('choice'))
        out['llm'] = surveyor.llm.status(nous_key)
        self._json(out)

    def _surv_recommendation(self):
        """The assessment at the end of the survey — how to set your system up."""
        email, stop = self._surv_guard()
        if stop: return
        profile = surveyor.pipeline.load_profile(email)
        self._json({'ok': True,
                    'recommendation': surveyor.recommendation.build(profile),
                    **surveyor.pipeline.public_profile(email, profile)})

    def _surv_fde_recommendations(self):
        """Return an authenticated, advisory-only registry routing trace."""
        email, stop = self._surv_guard()
        if stop: return
        profile = surveyor.pipeline.load_profile(email)
        states = surveyor.store.get_connector_states(email)
        context = surveyor.skills.recommendation_context(profile, states)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        limit = query.get('limit', [5])[0]
        self._json({'ok': True, **surveyor.fde_routing.recommend(context, limit)})

    def _surv_artifacts(self):
        """Inspectable source and compiled FDE context for the signed-in person."""
        email, stop = self._surv_guard()
        if stop: return
        self._json({'ok': True, 'artifacts': surveyor.pipeline.artifact_bundle(email),
                    'assessment': surveyor.pipeline.artifact_assessment(email),
                    'connector_catalog': surveyor.artifacts.connector_catalog()})

    def _surv_intent_miss(self, body):
        email, stop = self._surv_guard()
        if stop: return
        result = surveyor.pipeline.record_intent_miss(
            email, body.get('category'), body.get('correction'), body.get('effect'))
        self._json(result, 200 if result.get('ok') else 400)

    def _surv_approvals(self):
        email, stop = self._surv_guard()
        if stop: return
        self._json({'ok': True, 'approvals': surveyor.store.pending_approvals(email)})

    def _surv_capabilities(self):
        email, stop = self._surv_guard()
        if stop: return
        states = surveyor.store.get_connector_states(email)
        capabilities = []
        for name, capability in surveyor.capability_gateway.catalog().items():
            gate = surveyor.permissions.decide(name, states)
            capabilities.append({'name': name, **capability, 'decision': gate['decision'],
                                 'reason': gate['reason']})
        self._json({'ok': True, 'capabilities': capabilities})

    def _surv_skills(self):
        email, stop = self._surv_guard()
        if stop: return
        states = surveyor.store.get_connector_states(email)
        available = []
        for skill_id, skill in surveyor.skills.catalog().items():
            checks = [surveyor.permissions.decide(name, states)
                      for name in skill['required_capabilities']]
            available.append({'id': skill_id, **skill,
                              'available': all(check['decision'] == 'ALLOW' for check in checks)})
        self._json({'ok': True, 'skills': available})

    def _surv_activity(self):
        email, stop = self._surv_guard()
        if stop: return
        self._json({'ok': True, 'activity': surveyor.store.events(email, limit=20)})

    def _surv_preflight(self):
        email, stop = self._surv_guard()
        if stop: return
        self._json({'ok': True, 'preflight': surveyor_preflight.report()})

    def _surv_decide_approval(self, body):
        email, stop = self._surv_guard()
        if stop: return
        checkpoint = surveyor.store.get_pending_approval(email, str(body.get('id') or ''))
        if not checkpoint:
            self._json({'ok': False, 'error': 'approval not found or already decided'}, 404); return
        try:
            decision = surveyor.hitl_policy.decide(checkpoint, email, bool(body.get('approved')),
                                                    body.get('note', ''))
        except ValueError as exc:
            self._json({'ok': False, 'error': str(exc)}, 400); return
        if not surveyor.store.decide_approval(email, decision):
            self._json({'ok': False, 'error': 'approval not found or already decided'}, 404); return
        surveyor.store.log_event(email, 'approval_decided',
                                 {'id': decision['id'], 'status': decision['status']})
        self._json({'ok': True, 'approval': decision,
                    'resume': surveyor.hitl_policy.resume_instruction(checkpoint, decision)})

    def _surv_workspace(self):
        """Return one person's canonical workspace state, never another user's."""
        email, stop = self._surv_guard()
        if stop: return
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        workspace_id = str(query.get('id', [''])[0])
        if not workspace_id:
            self._json({'ok': False, 'error': 'workspace id is required'}, 400)
            return
        state = surveyor.store.get_workspace(email, workspace_id)
        if not state:
            legacy = surveyor.store.get_interface(email, workspace_id)
            if not legacy:
                self._json({'ok': False, 'error': 'workspace not found'}, 404)
                return
            definition = dict(legacy['definition'] or {})
            definition.update({'name': legacy['name'], 'description': legacy['description']})
            state = surveyor.workspace_state.from_interface(
                workspace_id, definition, surveyor.store.get_connector_states(email))
            surveyor.store.save_workspace(email, workspace_id, state)
        self._json({'ok': True, 'workspace': state})

    def _surv_alidora_map(self):
        """Return a safe, read-only Alidora map for the signed-in workspace owner."""
        email, stop = self._surv_guard()
        if stop: return
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        workspace_id = str(query.get('id', [''])[0])
        if not workspace_id:
            self._json({'ok': False, 'error': 'workspace id is required'}, 400)
            return
        state = surveyor.store.get_workspace(email, workspace_id)
        if not state:
            self._json({'ok': False, 'error': 'workspace not found'}, 404)
            return
        self._json({'ok': True, 'map': surveyor.alidora.map_payload(state)})

    def _surv_workspace_mutation(self, body):
        """Apply an allow-listed human workspace change to canonical state."""
        email, stop = self._surv_guard()
        if stop: return
        workspace_id = str(body.get('id') or '')
        state = surveyor.store.get_workspace(email, workspace_id)
        if not state:
            self._json({'ok': False, 'error': 'workspace not found'}, 404)
            return
        try:
            changed = surveyor.workspace_state.apply_mutation(
                state, body.get('mutation'), 'human')
        except ValueError as exc:
            self._json({'ok': False, 'error': str(exc)}, 400)
            return
        surveyor.store.save_workspace(email, workspace_id, changed)
        surveyor.store.log_event(email, 'workspace_mutated',
                                 {'id': workspace_id,
                                  'kind': body.get('mutation', {}).get('kind')})
        self._json({'ok': True, 'workspace': changed})

    def _surv_github_repositories(self):
        """Read-only GitHub summary through the first connector-native surface."""
        email, stop = self._surv_guard()
        if stop: return
        try:
            outcome = self._github_read_capability(email)
        except (surveyor.github_connector.ConnectorUnavailable,
                surveyor.vault.VaultUnavailable) as exc:
            self._surv_connector_runtime(email, 'github', 'needs_attention')
            self._json({'ok': False, 'error': str(exc)}, 503)
            return
        if not outcome['ok']:
            self._json(outcome, 409)
            return
        self._surv_connector_runtime(email, 'github', 'live')
        surveyor.store.log_event(email, 'github_repositories_read',
                                 {'count': len(outcome['result']['repositories'])})
        self._json({'ok': True, 'capability': outcome['capability'],
                    'permission': outcome['permission'], **outcome['result']})

    def _github_read_capability(self, email):
        """One credential-resolution boundary shared by direct and skill execution."""
        states = surveyor.store.get_connector_states(email)

        def read_repositories():
            # The gateway invokes this only after the connector permission is ALLOW.
            # Keep both secret resolution and network activity inside that boundary.
            stored = surveyor.store.get_secret(email, 'github')
            if not stored:
                raise surveyor.vault.VaultUnavailable(
                    'Connect GitHub with a token before Cordia can read repositories.')
            _secret_ref, ciphertext = stored
            token = surveyor.vault.from_environment().open(ciphertext)
            return surveyor.github_connector.list_repositories(token)

        return surveyor.capability_gateway.execute(
            'github.read_repositories', states,
            read_repositories)

    def _surv_execute_skill(self, body):
        """Execute an allow-listed skill only through its declared typed capability."""
        email, stop = self._surv_guard()
        if stop: return
        skill_id = str(body.get('id') or '')
        try:
            outcome = surveyor.skills.execute(
                skill_id, surveyor.store.get_connector_states(email),
                lambda capability: self._github_read_capability(email)
                if capability == 'github.read_repositories'
                else {'ok': False, 'error': 'skill capability is not implemented'})
        except (surveyor.github_connector.ConnectorUnavailable,
                surveyor.vault.VaultUnavailable) as exc:
            self._surv_connector_runtime(email, 'github', 'needs_attention')
            self._json({'ok': False, 'error': str(exc)}, 503)
            return
        if not outcome.get('ok'):
            self._json(outcome, 409)
            return
        result = outcome.get('result')
        repositories = result.get('repositories') if isinstance(result, dict) else None
        if skill_id != 'github_repository_review' or not isinstance(repositories, list):
            self._json({'ok': False, 'error': 'skill returned an unexpected result'}, 502)
            return
        repository_count = min(30, len(repositories))
        self._surv_connector_runtime(email, 'github', 'live')
        surveyor.store.log_event(email, 'skill_executed', {
            'id': skill_id, 'repository_count': repository_count})
        self._json({
            'ok': True,
            'skill_id': skill_id,
            'result': {'repository_count': repository_count},
        })

    def _surv_connector_runtime(self, email, connector_id, runtime_status):
        """Best-effort runtime health projection into every saved workspace."""
        for workspace_id, state in surveyor.store.workspaces(email):
            try:
                surveyor.store.save_workspace(
                    email, workspace_id,
                    surveyor.workspace_state.record_connector_runtime(
                        state, connector_id, runtime_status))
            except Exception:
                pass

    def _surv_github_token(self, body):
        """Validate then encrypt a user-entered GitHub token without returning it."""
        email, stop = self._surv_guard()
        if stop: return
        try:
            token = str(body.get('token') or '')
            validation = surveyor.github_connector.validate_token(token)
            ref, ciphertext = surveyor.vault.from_environment().seal(
                'github', token)
            surveyor.store.save_secret(ref, email, 'github', ciphertext)
            states = surveyor.artifacts.merge_connector_states(
                surveyor.store.get_connector_states(email), {'github': 'confirmed'})
            surveyor.store.save_connector_states(email, states)
            for workspace_id, state in surveyor.store.workspaces(email):
                surveyor.store.save_workspace(email, workspace_id,
                                              surveyor.workspace_state.refresh_connectors(state, states))
        except (ValueError, surveyor.vault.VaultUnavailable,
                surveyor.github_connector.ConnectorUnavailable) as exc:
            code = 422 if isinstance(exc, surveyor.github_connector.AuthorizationRejected) else 503
            self._json({'ok': False, 'error': str(exc)}, code)
            return
        self._surv_connector_runtime(email, 'github', 'live')
        surveyor.store.log_event(email, 'github_secret_configured',
                                 {'secret_ref': ref, 'repository_count': len(validation['repositories'])})
        self._json({'ok': True, 'secret_ref': ref, 'connector_state': 'confirmed',
                    'repository_limit': validation['repository_limit']})

    def _surv_connectors(self, body):
        """Store only explicit connector confirmations; authorization comes later."""
        email, stop = self._surv_guard()
        if stop: return
        states = surveyor.artifacts.merge_connector_states(
            surveyor.store.get_connector_states(email), body.get('connector_states'))
        surveyor.store.save_connector_states(email, states)
        for workspace_id, state in surveyor.store.workspaces(email):
            surveyor.store.save_workspace(email, workspace_id,
                                          surveyor.workspace_state.refresh_connectors(state, states))
        surveyor.store.log_event(email, 'connector_preferences_updated', {'ids': sorted(states)})
        self._json({'ok': True, 'connector_states': states,
                    'artifacts': surveyor.pipeline.artifact_bundle(email)})

    def _surv_export(self):
        """Survey answers as JSONL, for phase-2 analysis. Admin only — this is
        every participant's raw text, not just the requester's."""
        email, stop = self._surv_guard()
        if stop: return
        if not self._surv_is_admin(email):
            self._json({'ok': False, 'error': 'not authorised'}, 403); return
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        rows = (surveyor.store.export_profiles()
                if q.get('what', [''])[0] == 'profiles'
                else surveyor.store.export_answers())
        body = '\n'.join(json.dumps(r) for r in rows).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson')
        self.send_header('Content-Disposition',
                         'attachment; filename="cordia-survey-answers.jsonl"')
        self.send_header('Content-Length', str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _surv_is_admin(self, email):
        allowed = {e.strip().lower() for e in
                   (os.environ.get('CORDIA_ADMINS', '') or '').split(',') if e.strip()}
        allowed |= {os.environ.get('CORDIA_RATER_A', '').strip().lower(),
                    os.environ.get('CORDIA_RATER_B', '').strip().lower()}
        allowed.discard('')
        return email.lower() in allowed

    def _log_admin(self, email, route):
        try:
            import psycopg2
            dsn = os.environ.get('CORDIA_PG_DSN') or os.environ.get('DATABASE_URL')
            if not dsn:
                return
            with psycopg2.connect(dsn) as c, c.cursor() as cur:
                cur.execute(
                    "INSERT INTO admin_audit(email, route, ip, ua) VALUES(%s,%s,%s,%s)",
                    (email.lower(), route, self._client_ip(),
                     (self.headers.get('User-Agent', '') or '')[:200]))
        except Exception:
            pass

    def _surv_defaults(self, profile):
        return surveyor.adaptation.builder_defaults(profile)

    def _surv_save_interface(self, body):
        email, stop = self._surv_guard()
        if stop: return
        name = str(body.get('name', '')).strip()[:120] or 'Untitled interface'
        desc = str(body.get('description', ''))[:600]
        definition = body.get('definition')
        if not isinstance(definition, dict):
            self._json({'ok': False, 'error': 'definition must be an object'}, 400); return
        # str(None) is the string 'None', which is truthy — a JSON null id would
        # otherwise be read as an edit of an interface with that literal id, and
        # every "save new interface" would 404.
        existing = str(body.get('id') or '').strip() or None
        if existing and not surveyor.store.get_interface(email, existing):
            self._json({'ok': False, 'error': 'not found'}, 404); return
        iid = surveyor.store.save_interface(email, existing, name, desc, definition,
                                            body.get('theme'))
        workspace_definition = dict(definition)
        workspace_definition.update({'name': name, 'description': desc})
        workspace = surveyor.store.get_workspace(email, iid)
        if workspace:
            surveyor.store.save_workspace(
                email, iid,
                surveyor.workspace_state.merge_interface(workspace, workspace_definition))
        else:
            workspace = surveyor.workspace_state.from_interface(
                iid, workspace_definition, surveyor.store.get_connector_states(email))
            surveyor.store.save_workspace(email, iid, workspace)
        surveyor.store.log_event(email,
                                 'interface_updated' if existing else 'interface_created',
                                 {'id': iid, 'agents': len(definition.get('agents') or []),
                                  'tools': len(definition.get('tools') or [])})
        if not existing:
            # Record what we recommended, so it can later be compared against
            # whether it worked. outcomes.outcome_worked stays NULL until then.
            self._surv_record_outcome(email, definition)
        self._json({'ok': True, 'id': iid})

    def _surv_record_outcome(self, email, definition):
        """Best-effort write into the existing 6S outcomes table. Silent no-op
        for a learner with no submission to attach to — see store.record_recommendation."""
        try:
            surveyor.store.record_recommendation(email, definition)
        except Exception:
            pass

    def _surv_list_interfaces(self):
        email, stop = self._surv_guard()
        if stop: return
        profile = surveyor.pipeline.load_profile(email)
        self._json({'ok': True,
                    'interfaces': surveyor.store.list_interfaces(email),
                    'defaults': self._surv_defaults(profile)})

    def _surv_archive(self, body):
        email, stop = self._surv_guard()
        if stop: return
        iid = str(body.get('id') or '')
        ok = surveyor.store.archive_interface(email, iid, bool(body.get('archived', True)))
        self._json({'ok': ok}, 200 if ok else 404)

    def _surv_run(self, body):
        email, stop = self._surv_guard()
        if stop: return
        if not rate_ok(self._client_ip(), email, llm=True):
            self._json({'ok': False, 'error': 'run limit reached — wait 10 minutes'}, 429)
            return
        iface = surveyor.store.get_interface(email, str(body.get('id') or ''))
        if not iface:
            self._json({'ok': False, 'error': 'not found'}, 404); return
        prompt = str(body.get('input', ''))[:6000].strip()
        if not prompt:
            self._json({'ok': False, 'error': 'input required'}, 400); return
        profile = surveyor.pipeline.load_profile(email)
        workspace = surveyor.store.get_workspace(email, iface['id']) or {}
        system = surveyor.prompts.runtime_system(
            iface['definition'], surveyor.adaptation.soft_profile(profile),
            surveyor.pipeline.artifact_bundle(email), workspace)
        status = surveyor.llm.status(nous_key)
        try:
            out = self._surv_llm()(system, prompt, max_tokens=1200)
        except Exception as e:
            self._json({'ok': False, 'error': f'run failed: {e}'}, 502); return
        run_id = surveyor.store.add_run(iface['id'], email, prompt, out, {'llm': status['mode']})
        approval_step = next((step for step in (iface['definition'].get('workflow') or {}).get('steps', [])
                              if surveyor.hitl_policy.requires_approval(step)), None)
        checkpoint = surveyor.hitl_policy.create_checkpoint(run_id, approval_step, out) if approval_step else None
        if checkpoint:
            surveyor.store.save_approval(email, checkpoint)
        surveyor.store.log_event(email, 'interface_run',
                                 {'id': iface['id'], 'llm': status['mode']})
        self._json({'ok': True, 'output': out, 'llm': status, 'approval': checkpoint})

    def _surv_personalization(self, body):
        email, stop = self._surv_guard()
        if stop: return
        forced = bool(body.get('simple_mode_forced'))
        surveyor.store.set_simple_mode(email, forced)
        surveyor.store.log_event(email, 'simple_mode_forced', {'value': forced})
        self._json({'ok': True, 'simple_mode_forced': forced,
                    'personalization': surveyor.adaptation.mode()})

    def _surv_admin(self):
        """Debug view. Restricted — this exposes hidden criteria and evidence,
        which are explicitly not learner-facing."""
        email, stop = self._surv_guard()
        if stop: return
        if not self._surv_is_admin(email):
            self._json({'ok': False, 'error': 'not authorised'}, 403); return
        ip = self._client_ip()
        if not rate_ok(ip, email=email, admin=True):
            self._json({'ok': False, 'error': 'rate limit — wait 10 minutes'}, 429); return
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        target = (q.get('email', [email])[0] or email).strip().lower()
        try:
            profile = surveyor.pipeline.load_profile(target)
            cid = surveyor.store.open_conversation(target)
            self._json({'ok': True, 'email': target, 'profile': profile,
                        'public': surveyor.pipeline.public_profile(target, profile),
                        'messages': surveyor.store.messages(cid),
                        'adaptation': surveyor.adaptation.builder_defaults(profile),
                        'interfaces': surveyor.store.list_interfaces(target, True),
                        'runs': surveyor.store.runs(target),
                        'events': surveyor.store.events(target),
                        'llm': surveyor.llm.status(nous_key),
                        'personalization_mode': surveyor.adaptation.mode()})
        except Exception as e:
            self._json({'ok': False, 'error': 'surveyor unavailable: ' + str(e)}, 503)

    def _admin_users(self):
        email, stop = self._surv_guard()
        if stop: return
        if not self._surv_is_admin(email):
            self._json({'ok': False, 'error': 'not authorised'}, 403); return
        self._log_admin(email, 'admin/users')
        ip = self._client_ip()
        if not rate_ok(ip, email=email, admin=True):
            self._json({'ok': False, 'error': 'rate limit — wait 10 minutes'}, 429); return
        import psycopg2
        from psycopg2.extras import RealDictCursor
        dsn = os.environ.get('CORDIA_PG_DSN') or os.environ.get('DATABASE_URL')
        if not dsn:
            self._json({'ok': False, 'error': 'database not configured'}, 500); return
        users = []
        try:
            with psycopg2.connect(dsn) as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT a.email,
                           a.name,
                           to_timestamp(a.created) AS created_at,
                           COALESCE(s.cnt, 0) AS submissions,
                           COALESCE(c.cnt, 0) AS surveyor_conversations,
                           COALESCE(m.cnt, 0) AS surveyor_messages
                    FROM accounts a
                    LEFT JOIN (
                        SELECT user_ref, COUNT(*) AS cnt
                        FROM submissions
                        GROUP BY user_ref
                    ) s ON s.user_ref = a.email
                    LEFT JOIN (
                        SELECT email, COUNT(*) AS cnt
                        FROM surveyor_conversations
                        GROUP BY email
                    ) c ON c.email = a.email
                    LEFT JOIN (
                        SELECT c.email, COUNT(*) AS cnt
                        FROM surveyor_messages m
                        JOIN surveyor_conversations c ON c.id = m.conversation_id
                        GROUP BY c.email
                    ) m ON m.email = a.email
                    ORDER BY a.created DESC
                """)
                for r in cur.fetchall():
                    users.append({
                        'email': r['email'],
                        'name': r['name'],
                        'created_at': r['created_at'].isoformat() if r['created_at'] else '',
                        'submissions': int(r['submissions'] or 0),
                        'surveyor_conversations': int(r['surveyor_conversations'] or 0),
                        'surveyor_messages': int(r['surveyor_messages'] or 0),
                    })
        except Exception as e:
            self._json({'ok': False, 'error': str(e)}, 500); return
        self._json({'ok': True, 'users': users})

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
        token = self._token()
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
        token = self._token()
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
        token = self._token()
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
            shadow = embedding_scoring.score_course(course_id, rows) if embedding_scoring else None
            if shadow is None:
                raise RuntimeError('embedding shadow scoring is unavailable')
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

    def do_PATCH(self):
        # BaseHTTPRequestHandler routes nothing here by default — the account
        # profile update path 501'd until this existed.
        if self.path.split('?')[0] == '/account/profile':
            self._account_profile()
        else:
            self._json({'error': 'not found'}, 404)

    def do_POST(self):
        p = self.path.split('?')[0]
        try:
            body = self._body()
        except Exception as e:
            self._json({'error': str(e)}, 400); return
        self._surv_body = body if isinstance(body, dict) else {}
        if p == '/train/respond':
            self._respond(body)
        elif p == '/surveyor/message':
            self._surv_message(body)
        elif p == '/surveyor/interface':
            self._surv_save_interface(body)
        elif p == '/surveyor/archive':
            self._surv_archive(body)
        elif p == '/surveyor/run':
            self._surv_run(body)
        elif p == '/surveyor/personalization':
            self._surv_personalization(body)
        elif p == '/surveyor/connectors':
            self._surv_connectors(body)
        elif p == '/surveyor/intent-miss':
            self._surv_intent_miss(body)
        elif p == '/surveyor/workspace/mutate':
            self._surv_workspace_mutation(body)
        elif p == '/surveyor/approval/decision':
            self._surv_decide_approval(body)
        elif p == '/surveyor/skill/execute':
            self._surv_execute_skill(body)
        elif p == '/surveyor/github/token':
            self._surv_github_token(body)
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
            # Ordinary sign-out ends the session but keeps the device trusted —
            # otherwise "log out" would silently mean "email me a code next
            # time", which is the friction this exists to remove. Passing
            # forget_device makes it a real sign-out for shared machines.
            tok = self._token() or str(body.get('token', ''))
            if body.get('forget_device'):
                me = auth.whoami(tok)
                if me:
                    auth.forget_devices(me['email'])
            auth.logout(tok)
            self._clear_session_cookie()
            self._json({'ok': True})
        elif p == '/auth/session':
            # NOTE: must reuse the already-parsed body. do_POST consumed the
            # request stream at the top; calling self._body() again blocks on
            # rfile.read(Content-Length) forever (bytes already read), which
            # hung every /auth/session call until Apache's proxy timeout —
            # seen in the logs as AH01102 504s and broken auth-gate checks.
            token = self._token() or self._surv_body.get('token', '')
            me = auth.whoami(token)
            if not me:
                self._json({'ok': False, 'authed': False}, 401); return
            self._json({'ok': True, 'authed': True, 'user': me})
        elif p == '/auth/enroll':
            self._enroll()
        elif p == '/auth/forgot-password':
            self._forgot_password()
        elif p == '/auth/reset-password':
            self._reset_password()
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
        if fn is auth.signup:
            ok, msg, dev_code = fn(email, name, pw)
            session = None
        else:
            # A device that has already completed the code flow for this account
            # gets a session straight back and never sees a code. The password
            # was still checked inside login().
            device = str(body.get('device', ''))[:120]
            ok, msg, dev_code, session = fn(email, pw, device)
        out = {'ok': ok, 'msg': msg}
        if dev_code: out['dev_code'] = dev_code
        if session:
            out['token'] = session
            out['skipped_code'] = True
            self._set_session_cookie(session)
        self._json(out, 200 if ok else 400)

    def _auth_verify(self, fn, body):
        ip = self._client_ip()
        email = str(body.get('email', ''))[:200]
        if not rate_ok(ip, email.lower() or None):
            self._json({'ok': False, 'msg': 'too many attempts — wait 10 minutes and try again'}, 429)
            return
        code = str(body.get('code', ''))[:12]
        ok, msg, token, device = fn(email, code)
        out = {'ok': ok, 'msg': msg}
        if token:
            out['token'] = token
            # The HttpOnly cookie is the canonical session — the browser sends
            # it automatically on every request, so no page JS ever has to
            # store or attach a token again.
            self._set_session_cookie(token)
        # Returned once, on the request that proved inbox control. The browser
        # keeps it and presents it on the next sign-in to skip the code.
        if device: out['device'] = device
        self._json(out, 200 if ok else 400)

    def _forgot_password(self):
        ip = self._client_ip()
        body = self._surv_body if isinstance(self._surv_body, dict) else {}
        email = str(body.get('email', '')).strip().lower()
        if not email:
            self._json({'ok': False, 'msg': 'email required'}, 400); return
        if not rate_ok(ip, email):
            self._json({'ok': False, 'msg': 'too many attempts — wait 10 minutes'}, 429); return
        ok, msg = auth.request_password_reset(email)
        self._json({'ok': ok, 'msg': msg}, 200 if ok else 400)

    def _reset_password(self):
        body = self._surv_body if isinstance(self._surv_body, dict) else {}
        email = str(body.get('email', '')).strip().lower()
        code = str(body.get('code', '')).strip()
        new_password = str(body.get('new_password', '')).strip()
        if not email or not code or not new_password:
            self._json({'ok': False, 'msg': 'email, code, and new_password required'}, 400); return
        if len(new_password) < 6:
            self._json({'ok': False, 'msg': 'password must be at least 6 characters'}, 400); return
        ok, msg = auth.reset_password(email, code, new_password)
        self._json({'ok': ok, 'msg': msg}, 200 if ok else 400)

    def _enroll(self):
        ip = self._client_ip()
        if not rate_ok(ip, None):
            self._json({'ok': False, 'msg': 'too many attempts'}, 429); return
        token = self._token()
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

    def _account_profile(self):
        token = self._token()
        me = auth.whoami(token) if token else None
        if not me:
            self._json({'ok': False, 'error': 'sign in required'}, 401); return
        import urllib.parse as up
        method = self.command.upper()
        qs = up.parse_qs(up.urlparse(self.path).query)
        if method == 'GET':
            with lock, auth._conn() as c, c.cursor() as cur:
                cur.execute('SELECT avatar_url,display_name,bio,locale FROM accounts WHERE email=%s', (me['email'],))
                row = cur.fetchone() or (None, None, None, 'en')
                self._json({'ok': True, 'email': me['email'], 'name': me['name'],
                            'avatar_url': row[0], 'display_name': row[1],
                            'bio': row[2], 'locale': row[3]})
        elif method == 'PATCH':
            length = int(self.headers.get('Content-Length', '0') or '0')
            body = json.loads(self.rfile.read(length) or '{}')
            fields = {}
            for key in ('display_name', 'bio', 'locale'):
                if key in body: fields[key] = str(body.get(key, '') or '')
            if 'avatar_url' in body:
                url = str(body.get('avatar_url', '') or '')
                if url and not re.match(r'^https?://[^\s]+$', url):
                    self._json({'ok': False, 'error': 'avatar_url must be a valid URL'}, 400); return
                fields['avatar_url'] = url
            if not fields:
                self._json({'ok': False, 'error': 'nothing to update'}, 400); return
            set_sql = ', '.join(f'{k}=%s' for k in fields.keys())
            with lock, auth._conn() as c, c.cursor() as cur:
                cur.execute(f'UPDATE accounts SET {set_sql} WHERE email=%s', (*fields.values(), me['email']))
            self._json({'ok': True, 'updated': list(fields.keys())})
        else:
            self._json({'error': 'method not allowed'}, 405)

    def _my_access(self):
        token = self._token()
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
        token = self._token()
        me = auth.whoami(token) if token else None
        if not me:
            self._json({'ok': False, 'msg': 'sign in required'}, 401); return
        try:
            from sixs.profile_compiler import compile_profile
            from sixs.agent_manifest import build_manifest
            from sixs import selfreport
        except Exception as e:
            self._json({'ok': False, 'msg': f'manifest unavailable: {e}'}, 503); return
        import urllib.parse as up
        q = up.parse_qs(up.urlparse(self.path).query)
        industries = [i for i in q.get('industries', [''])[0].split(',') if i][:20]
        profile = compile_profile(me['email'])
        if not profile:
            self._json({'ok': False, 'msg': 'no score data yet — take the exam first'}, 404); return
        # survey gate: the assessment is "paid for" with the exit survey
        rows = read_all(CORPUS)
        survey_rec = selfreport.latest_survey(rows, me['email'])
        if not survey_rec:
            self._json({'ok': False, 'survey_required': True,
                        'msg': 'complete the 90-second exit survey to unlock your assessment'}, 402); return

        # The Surveyor profile decides how the assigned system behaves. Loaded
        # softly: Surveyor is an optional module here, and a learner may hold a
        # certificate without ever having talked to it. Either way the manifest
        # still builds — it just reports survey_led false and defaults oversight
        # to the cautious end rather than inventing a preference.
        surveyor_profile = None
        try:
            from surveyor import pipeline as surv_pipeline
            from surveyor import scenarios as surv_scenarios
            surveyor_profile = surv_pipeline.load_profile(me['email'])
            if surveyor_profile:
                # Scenario choices beat stated answers on any dimension they
                # cross-check — the single enforcement point for "the scenario
                # wins", applied here so oversight follows what they'd actually do.
                surveyor_profile = dict(surveyor_profile)
                surveyor_profile['signals'] = surv_scenarios.effective(surveyor_profile)
        except Exception as e:
            print(f'surveyor profile unavailable for manifest (non-fatal): {e}', file=sys.stderr)

        self._json({'ok': True, 'profile': profile,
                    'selfreport': selfreport.score_selfreport(
                        survey_rec, profile.get('latest_final_composite')),
                    'manifest': build_manifest(profile, industries, surveyor_profile)})

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
        token = self._token()
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
        # Identity comes from the session, never from the request body.
        #
        # This previously read `learner` out of the body and only overrode it if
        # a valid token happened to be present, so an unauthenticated caller
        # could post an answer attributed to anyone. Because _rateable_candidates
        # and score_course both take the LATEST row per (learner, block), that
        # let a stranger overwrite a real learner's exam answers — changing their
        # certification result, poisoning the kappa rating pool, and corrupting
        # the corpus. Confirmed exploitable against production before this fix.
        #
        # Anonymous practice is deliberately still allowed: no token simply means
        # the row is filed under 'anon' and belongs to nobody. What is no longer
        # possible is claiming to be somebody.
        token = self._token() or str(body.get('token', ''))
        me = auth.whoami(token) if token else None
        learner = me['email'] if me else 'anon'
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
        token = self._token()
        me = auth.whoami(token) if token else None
        if not me:
            self._json({'ok': False, 'msg': 'sign in required'}, 401); return
        # The feedback comes AFTER the CordiaAIE, not alongside it. Three of its
        # six questions ask the learner to look back on answers they have
        # already written and scored — "how clear were you before you started",
        # "did the exercises read you the way you meant", "would your answers
        # work as written". Taken before the exam they are speculation, and
        # `calibration` in particular is meaningless: it is the distance between
        # a self-assessment and a measured result that does not exist yet.
        #
        # A certificate is the cheap proof of completion. Falling back to block
        # coverage keeps anyone who finished the work but never opened their
        # result from being locked out of their own assessment.
        if not _completed_course(me['email'], 'aie1'):
            self._json({'ok': False, 'exam_required': True,
                        'msg': 'finish the CordiaAIE first — these questions ask you to '
                               'look back on answers you have already written'}, 409); return
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
        token = self._token()
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
    """No-op. The marketing pipeline it used to POST to was removed — dead
    code for lifecycle email automation that never shipped."""
    pass


import urllib.parse


class Server(ThreadingHTTPServer):
    """Threaded so one slow request cannot stall the site.

    This was a plain HTTPServer, which serialises every request. call_llm has a
    90s timeout, so a single live-environment call (and now a single Surveyor
    turn) blocked login, the exam and the payment webhook for up to a minute and
    a half. Shared mutable state was audited before this changed: rate_ok holds
    `lock` around the _rl buckets, append/read_all hold it around the corpus
    jsonl, and psycopg2 connections are opened per call rather than shared. No
    module-level caches or `global` statements exist in this process.

    daemon_threads so a hung upstream request cannot block shutdown."""
    daemon_threads = True


def _housekeeping():
    """Purge expired sessions, login codes and pending signups.

    Runs at startup and daily. whoami() already rejects an expired session, so
    this is hygiene rather than a fix: it stops the tables growing without
    bound and shortens the history a database compromise would expose."""
    while True:
        try:
            counts = auth.purge_expired()
            if any(counts.values()):
                print(f'purged expired rows: {counts}', file=sys.stderr)
        except Exception as e:
            print(f'housekeeping skipped ({type(e).__name__}: {e})', file=sys.stderr)
        time.sleep(24 * 60 * 60)


if __name__ == '__main__':
    print(f'cordia-training backend on :{PORT}')
    threading.Thread(target=_housekeeping, daemon=True).start()
    Server((BIND, PORT), H).serve_forever()
