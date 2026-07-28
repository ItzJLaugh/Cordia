#!/usr/bin/env python3
"""cordia-engineer — Building Department agent.
Polls HiveBus log 'engineer' for task_assign messages, runs the requested
skill, posts the result back to Hive. Skills are mandatory: every task runs
through exactly one skill. Claude Code is the coding engine; this agent is
the disciplined wrapper around it.

Skills:
  /code-review   — review recent changes or a path; findings, not rewrites
  /build-fix     — diagnose + fix a build/runtime error, verify by re-running
  /implement     — implement a described change in the Cordia codebase
  /test-run      — run the service checks and report pass/fail
  /status        — report what this agent can see and touch
"""
import json, os, re, subprocess, sys, time, urllib.request

HIVE = os.environ.get('CORDIA_HIVE', 'http://100.73.131.108:9999')
SOUL = os.environ.get('CORDIA_SOUL', 'http://100.73.131.108:9992')
CLAUDE = os.environ.get('CLAUDE_BIN', '/root/.local/bin/claude')
NAME = 'engineer'
POLL = 5
WORKDIRS = ['/opt/cordia/backend', '/opt/cordia/web']
STATE = os.path.expanduser('~/.cordia-engineer-seen.json')

SKILLS = {
    'code-review': 'Review code changes or a path; report findings only',
    'build-fix': 'Diagnose and fix a build or runtime error, then verify',
    'implement': 'Implement a described change in the Cordia codebase',
    'test-run': 'Run service checks and report pass/fail',
    'status': 'Report agent reach and workdirs',
}

# ---------------- hive helpers ----------------

def hive_get(path):
    return json.loads(urllib.request.urlopen(HIVE + path, timeout=15).read())

def hive_post(path, obj):
    req = urllib.request.Request(HIVE + path, data=json.dumps(obj).encode(),
                                 headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def report(task_id, skill, ok, text):
    hive_post('/hive/message', {'from': NAME, 'to': 'soul',
              'type': 'task_complete' if ok else 'task_failed',
              'text': text[:40000],
              'meta': {'task_id': task_id, 'skill': skill, 'agent': NAME}})

# ---------------- skill runner ----------------

def claude(prompt, workdir, max_turns=10, timeout=600):
    """One print-mode Claude call. Returns (ok, output)."""
    try:
        r = subprocess.run([CLAUDE, '-p', prompt, '--model', 'opus',
                            '--max-turns', str(max_turns),
                            '--allowedTools', 'Read,Write,Edit,Bash',
                            '--output-format', 'text'],
                           cwd=workdir, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or '') + (('\n[stderr]\n' + r.stderr) if r.stderr else '')
        return r.returncode == 0, out.strip()
    except subprocess.TimeoutExpired:
        return False, 'claude timed out'
    except FileNotFoundError:
        return False, f'claude not found at {CLAUDE}'

def run_skill(skill, text):
    if skill == 'status':
        lines = [f'agent: {NAME}', f'hive: {HIVE}', f'claude: {CLAUDE} '
                 + ('present' if os.path.exists(CLAUDE) else 'MISSING')]
        for w in WORKDIRS:
            lines.append(f'{w}: ' + ('ok' if os.path.isdir(w) else 'missing'))
        return True, '\n'.join(lines)

    if skill == 'test-run':
        checks = [('training', 'http://127.0.0.1:9995/train/status'),
                  ('hive', HIVE + '/hive/status'),
                  ('soul', SOUL + '/soul/status')]
        out = []
        ok_all = True
        for name, url in checks:
            try:
                d = json.loads(urllib.request.urlopen(url, timeout=5).read())
                out.append(f'{name}: ok {json.dumps(d)[:120]}')
            except Exception as e:
                ok_all = False
                out.append(f'{name}: FAIL {e}')
        return ok_all, '\n'.join(out)

    if skill == 'code-review':
        prompt = ("You are the Cordia engineer agent running /code-review. "
                  "Review the code in this repo for real defects: bugs, security issues, "
                  "broken routes, dead code. Report findings as a numbered list with file:line. "
                  "Do NOT rewrite anything. Task: " + (text or 'review recent state of the repo'))
        return claude(prompt, '/opt/cordia', max_turns=8)

    if skill == 'build-fix':
        prompt = ("You are the Cordia engineer agent running /build-fix. "
                  "Diagnose and fix the following build/runtime problem in this codebase. "
                  "Make the minimal change, then verify by re-running the failing command. "
                  "Report: root cause, files changed, verification output. Problem: " + text)
        return claude(prompt, '/opt/cordia', max_turns=12)

    if skill == 'implement':
        prompt = ("You are the Cordia engineer agent running /implement. "
                  "Implement exactly the following change in this codebase. Minimal diff, "
                  "match existing style, verify it loads/compiles, report files changed. "
                  "Change: " + text)
        return claude(prompt, '/opt/cordia', max_turns=15)

    return False, f'unknown skill {skill}'

# ---------------- main loop ----------------

def load_seen():
    try: return set(json.load(open(STATE)))
    except Exception: return set()

def save_seen(s):
    json.dump(list(s)[-500:], open(STATE, 'w'))

def register():
    try:
        hive_post_soul = urllib.request.Request(
            SOUL + '/soul/register',
            data=json.dumps({'agent': NAME, 'skills': SKILLS}).encode(),
            headers={'Content-Type': 'application/json'})
        print(urllib.request.urlopen(hive_post_soul, timeout=10).read().decode())
    except Exception as e:
        print('register failed (will retry on boot only):', e)

def main():
    register()
    seen = load_seen()
    print(f'{NAME} online — {len(SKILLS)} skills, polling {HIVE}')
    while True:
        try:
            rows = hive_get(f'/hive/messages?log={NAME}&limit=20').get('messages', [])
            for m in rows:
                if m.get('type') != 'task_assign' or m['id'] in seen:
                    continue
                seen.add(m['id'])
                skill = m.get('meta', {}).get('skill', '')
                task_id = m.get('meta', {}).get('task_id', m['id'])
                print(f"[task {task_id}] /{skill}: {m.get('text','')[:80]}")
                ok, out = run_skill(skill, m.get('text', ''))
                report(task_id, skill, ok, out)
                print(f"[task {task_id}] {'done' if ok else 'FAILED'}")
            save_seen(seen)
        except Exception as e:
            print('poll error:', e)
        time.sleep(POLL)

if __name__ == '__main__':
    main()
