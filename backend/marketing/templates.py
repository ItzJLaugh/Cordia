"""Cordia marketing — strings-only email renderer.

Templates live in /opt/cordia/backend/templates/email/<kind>.{txt,html}
Plain Python format-string placeholders: {name}, {score}, {track}, etc.

No Jinja dependency — keeps deploy footprint tight and matches
Cordia's existing stdlib-only services.
"""
import os, re

TPL_DIR = '/opt/cordia/backend/templates/email'

CACHE = {}

ALLOWED_VARS = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]{0,40}$')

BASE_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>{subject}</title></head>
<body style="font-family:Georgia,serif;color:#2d321e;max-width:560px;margin:0 auto;padding:24px">
<div style="border-bottom:1px solid #ddd6c4;padding-bottom:14px;margin-bottom:22px">
  <div style="font-family:'Inter',sans-serif;font-size:11px;letter-spacing:.18em;color:#7a7a68;text-transform:uppercase">Cordia</div>
</div>
{body}
<div style="margin-top:30px;padding-top:14px;border-top:1px solid #ddd6c4;font-family:'Inter',sans-serif;font-size:11px;color:#9a9a8a">
  Cordia · jackson@cordiacode.com · <a href="https://cordiacode.com" style="color:#7a7a68">cordiacode.com</a>
  <br><a href="{unsubscribe_url}" style="color:#9a9a8a">Unsubscribe</a>
</div></body></html>"""


def _safe_format(template, vars_):
    """Only allow whitelisted keys; missing -> empty."""
    safe = {k: ('' if v is None else str(v)) for k, v in vars_.items() if ALLOWED_VARS.match(k)}
    try:
        return template.format(**safe)
    except Exception as e:
        return f'[template render error: {e}]'


def _load(name, ext):
    if (name, ext) in CACHE: return CACHE[(name, ext)]
    path = os.path.join(TPL_DIR, f'{name}.{ext}')
    if not os.path.exists(path):
        body = f'[missing template: {name}]'
    else:
        body = open(path).read()
    CACHE[(name, ext)] = body
    return body


def render(kind, vars_, kind_to_name=None):
    """Return {'subject','text','html'} for a kind. vars_ includes 'subject' key."""
    name = (kind_to_name or {}).get(kind, kind)
    subject = vars_.get('subject') or f'Cordia: {kind.replace("_"," ").title()}'
    txt = _load(name, 'txt')
    if not txt.startswith('[missing'):
        txt = _safe_format(txt, vars_)
    inner_html = _load(name, 'html')
    if inner_html.startswith('[missing'):
        # fall back to text wrapped in a <pre>
        inner_html = f'<pre style="white-space:pre-wrap;font-family:inherit">{txt}</pre>'
    else:
        inner_html = _safe_format(inner_html, vars_)
    unsub = vars_.get('unsubscribe_url', 'https://cordiacode.com/unsubscribe')
    html = BASE_HTML.format(subject=subject, body=inner_html, unsubscribe_url=unsub)
    return {'subject': subject, 'text': txt, 'html': html}
