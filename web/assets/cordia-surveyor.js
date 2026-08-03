/* Cordia Surveyor — the conversational intake window.

   A modal rather than a page, because Surveyor should be summonable from
   wherever someone already is. Include it anywhere:

     <script src="assets/cordia-surveyor.js"></script>

   and call Cordia.surveyor.open(), or add data-surveyor to any element to have
   it open on click. The shell's nav entry uses the latter.

   The window renders honestly: if the backend reports the model is offline it
   says so, rather than passing deterministic placeholder text off as a
   conversation. */
(function () {
  'use strict';

  var API = location.hostname === 'localhost' ? 'http://127.0.0.1:9995' : '';
  var root = null, listEl = null, inputEl = null, sendEl = null, statusEl = null;
  var busy = false, opened = false;

  function token() { return localStorage.getItem('cordia-token') || ''; }

  function api(path, body) {
    return fetch(API + path, {
      method: body ? 'POST' : 'GET',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token() },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      return r.json().catch(function () { return {}; })
        .then(function (d) { return { code: r.status, data: d }; });
    });
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function clock(iso) {
    var d = iso ? new Date(iso.replace(' ', 'T') + (/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? '' : 'Z')) : new Date();
    if (isNaN(d)) d = new Date();
    return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  }

  var CSS = [
    '.sv-veil{position:fixed;inset:0;z-index:900;background:rgba(11,11,11,.34);',
    '  backdrop-filter:blur(5px);-webkit-backdrop-filter:blur(5px);opacity:0;',
    '  transition:opacity .22s var(--ease-out,ease);display:flex;align-items:center;',
    '  justify-content:center;padding:24px}',
    '.sv-veil[data-open="1"]{opacity:1}',
    // The [hidden] attribute is not enough on its own: the UA stylesheet rule
    // [hidden]{display:none} is a single attribute selector, so `.sv-veil`
    // setting display:flex outranks it. Without this the closed modal stayed
    // laid out at opacity 0, position:fixed inset:0 z-index:900 — an invisible
    // sheet over the whole page that swallowed every click. pointer-events is
    // belt and braces for the 240ms between the fade starting and hidden being
    // applied.
    '.sv-veil[hidden]{display:none}',
    '.sv-veil[data-open="0"]{pointer-events:none}',
    '.sv-win{width:min(560px,100%);max-height:min(760px,92vh);display:flex;flex-direction:column;',
    '  background:var(--c-surface,#fff);border-radius:var(--r-lg,20px);overflow:hidden;',
    '  box-shadow:0 24px 64px -12px rgba(11,11,11,.30),0 2px 8px rgba(11,11,11,.08);',
    '  transform:translateY(10px) scale(.985);opacity:0;',
    '  transition:transform .26s var(--ease-overshoot,ease),opacity .2s ease}',
    '.sv-veil[data-open="1"] .sv-win{transform:none;opacity:1}',
    '.sv-head{display:flex;align-items:center;gap:12px;padding:16px 18px;',
    '  border-bottom:1px solid var(--c-hair,rgba(11,11,11,.08));flex:0 0 auto}',
    '.sv-mark{width:38px;height:38px;border-radius:50%;background:var(--c-moss,#4A5A42);',
    '  display:grid;place-items:center;flex:0 0 auto}',
    '.sv-mark svg{width:20px;height:20px;fill:none;stroke:#fff;stroke-width:1.6}',
    '.sv-id{flex:1;min-width:0}',
    '.sv-name{font-family:var(--f-title,Georgia,serif);font-size:var(--t-md,17px);',
    '  color:var(--c-ink,#0B0B0B);line-height:1.2}',
    '.sv-state{font-family:var(--f-label,sans-serif);font-size:var(--t-xs,11px);',
    '  color:var(--c-ink-3,#666);display:flex;align-items:center;gap:5px;margin-top:2px}',
    '.sv-dot{width:6px;height:6px;border-radius:50%;background:var(--c-moss,#4A5A42)}',
    '.sv-dot[data-off="1"]{background:#B08A3E}',
    '.sv-x{border:0;background:transparent;cursor:pointer;width:32px;height:32px;border-radius:50%;',
    '  color:var(--c-ink-3,#666);font-size:17px;line-height:1;display:grid;place-items:center}',
    '.sv-x:hover{background:var(--c-wash,#F6F7F4);color:var(--c-ink,#0B0B0B)}',
    '.sv-body{flex:1 1 auto;overflow-y:auto;padding:18px;display:flex;flex-direction:column;gap:14px;',
    '  background:var(--c-wash,#F6F7F4)}',
    '.sv-row{display:flex;flex-direction:column;max-width:82%}',
    '.sv-row[data-who="user"]{align-self:flex-end;align-items:flex-end}',
    '.sv-bub{padding:10px 14px;border-radius:14px;font-size:var(--t-sm,13px);',
    '  line-height:var(--lh-body,1.6);white-space:pre-wrap;word-wrap:break-word}',
    '.sv-row[data-who="assistant"] .sv-bub{background:#fff;color:var(--c-ink,#0B0B0B);',
    '  border-bottom-left-radius:5px;box-shadow:0 1px 2px rgba(11,11,11,.06)}',
    '.sv-row[data-who="user"] .sv-bub{background:var(--c-moss,#4A5A42);color:#fff;',
    '  border-bottom-right-radius:5px}',
    '.sv-time{font-family:var(--f-label,sans-serif);font-size:10px;color:var(--c-ink-4,#999);',
    '  margin-top:4px;padding:0 4px}',
    '.sv-typing{display:flex;gap:4px;padding:12px 14px;background:#fff;border-radius:14px;',
    '  border-bottom-left-radius:5px;width:fit-content}',
    '.sv-typing i{width:6px;height:6px;border-radius:50%;background:var(--c-ink-4,#999);',
    '  animation:svb 1.2s infinite}',
    '.sv-typing i:nth-child(2){animation-delay:.15s}.sv-typing i:nth-child(3){animation-delay:.3s}',
    '@keyframes svb{0%,60%,100%{opacity:.28;transform:translateY(0)}30%{opacity:1;transform:translateY(-3px)}}',
    '.sv-note{font-family:var(--f-label,sans-serif);font-size:var(--t-xs,11px);',
    '  color:#7A5B2E;background:#FBF6EC;border-radius:8px;padding:8px 11px;line-height:1.45}',
    '.sv-chips{display:flex;flex-wrap:wrap;gap:6px;margin:-4px 0 2px;padding:0 2px}',
    '.sv-chip{border:1px solid var(--c-hair,rgba(11,11,11,.14));background:#fff;',
    '  border-radius:var(--r-pill,999px);padding:7px 13px;font-size:var(--t-xs,11px);',
    '  font-family:var(--f-label,sans-serif);color:var(--c-ink-2,#333);cursor:pointer;',
    '  transition:border-color .15s,color .15s}',
    '.sv-chip:hover{border-color:var(--c-moss,#4A5A42);color:var(--c-moss,#4A5A42)}',
    '.sv-chip:focus-visible{outline:2px solid var(--c-moss,#4A5A42);outline-offset:1px}',
    '.sv-foot{flex:0 0 auto;border-top:1px solid var(--c-hair,rgba(11,11,11,.08));background:#fff}',
    '.sv-compose{display:flex;gap:8px;padding:12px 14px;align-items:flex-end}',
    '.sv-compose textarea{flex:1;border:1px solid var(--c-hair,rgba(11,11,11,.12));',
    '  border-radius:12px;padding:10px 12px;font:inherit;font-size:var(--t-sm,13px);resize:none;',
    '  max-height:110px;min-height:40px;line-height:1.45;color:var(--c-ink,#0B0B0B);background:#fff}',
    '.sv-compose textarea:focus{outline:2px solid var(--c-moss,#4A5A42);outline-offset:-1px;border-color:transparent}',
    '.sv-send{border:0;background:var(--c-moss,#4A5A42);color:#fff;border-radius:12px;',
    '  padding:0 16px;height:40px;cursor:pointer;font-family:var(--f-label,sans-serif);',
    '  font-size:var(--t-xs,11px);letter-spacing:var(--tr-caps,.16em);text-transform:uppercase}',
    '.sv-send[disabled]{opacity:.45;cursor:default}',
    '.sv-acts{display:flex;gap:8px;padding:0 14px 13px;flex-wrap:wrap}',
    '.sv-act{border:1px solid var(--c-hair,rgba(11,11,11,.12));background:#fff;border-radius:var(--r-pill,999px);',
    '  padding:7px 13px;font-size:var(--t-xs,11px);font-family:var(--f-label,sans-serif);',
    '  color:var(--c-ink-2,#333);cursor:pointer;display:inline-flex;align-items:center;gap:6px}',
    '.sv-act:hover{border-color:var(--c-moss,#4A5A42);color:var(--c-moss,#4A5A42)}',
    '@media (max-width:560px){.sv-veil{padding:0}.sv-win{width:100%;max-height:100vh;height:100vh;',
    '  border-radius:0}.sv-row{max-width:88%}}',
    '@media (prefers-reduced-motion:reduce){.sv-veil,.sv-win{transition:none}.sv-typing i{animation:none}}'
  ].join('\n');

  var MARK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5 13.9 9l5.6.4-4.3 3.6 1.4 5.4L12 15.6 7.4 18.4l1.4-5.4L4.5 9.4 10.1 9z" stroke-linejoin="round"/></svg>';

  function build() {
    var style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);

    root = document.createElement('div');
    root.className = 'sv-veil';
    root.setAttribute('data-open', '0');
    root.hidden = true;
    root.innerHTML =
      '<div class="sv-win" role="dialog" aria-modal="true" aria-label="Surveyor">' +
        '<div class="sv-head">' +
          '<div class="sv-mark">' + MARK + '</div>' +
          '<div class="sv-id"><div class="sv-name">Surveyor</div>' +
            '<div class="sv-state" id="svState"><span class="sv-dot"></span><span>Online</span></div></div>' +
          '<button class="sv-x" id="svClose" type="button" aria-label="Close Surveyor">&#10005;</button>' +
        '</div>' +
        '<div class="sv-body" id="svBody" aria-live="polite"></div>' +
        '<div class="sv-foot">' +
          '<div class="sv-compose">' +
            '<textarea id="svInput" rows="1" placeholder="Type your answer…" ' +
              'aria-label="Your message"></textarea>' +
            '<button class="sv-send" id="svSend" type="button">Send</button>' +
          '</div>' +
          '<div class="sv-acts">' +
            '<button class="sv-act" data-act="refine" type="button">Refine my profile</button>' +
            '<button class="sv-act" data-act="build" type="button">Build my workspace</button>' +
            '<button class="sv-act" data-act="certs" type="button">Show recommended certification</button>' +
          '</div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(root);

    listEl = root.querySelector('#svBody');
    inputEl = root.querySelector('#svInput');
    sendEl = root.querySelector('#svSend');
    statusEl = root.querySelector('#svState');

    root.querySelector('#svClose').addEventListener('click', close);
    root.addEventListener('mousedown', function (e) { if (e.target === root) close(); });
    addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && opened) close();
    });
    // Wrapped, not passed directly: addEventListener hands the click Event to
    // its listener, which send() would take as `preset` and post as the user's
    // answer. That stored "{'isTrusted': true}" as a real survey response.
    sendEl.addEventListener('click', function () { send(); });
    inputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    });
    inputEl.addEventListener('input', function () {
      inputEl.style.height = 'auto';
      inputEl.style.height = Math.min(110, inputEl.scrollHeight) + 'px';
    });
    root.querySelector('.sv-acts').addEventListener('click', function (e) {
      var b = e.target.closest('.sv-act');
      if (!b) return;
      var a = b.dataset.act;
      if (a === 'rec') location.href = 'profile.html';
      else if (a === 'build') location.href = 'builder.html';
      else if (a === 'certs') location.href = 'certifications.html';
      else { inputEl.focus(); }
    });
  }

  function bubble(role, text, iso) {
    var row = document.createElement('div');
    row.className = 'sv-row';
    row.setAttribute('data-who', role === 'user' ? 'user' : 'assistant');
    row.innerHTML = '<div class="sv-bub">' + esc(text) + '</div>' +
                    '<div class="sv-time">' + clock(iso) + '</div>';
    listEl.appendChild(row);
    listEl.scrollTop = listEl.scrollHeight;
    return row;
  }

  function typing(on) {
    var t = listEl.querySelector('#svTyping');
    if (on && !t) {
      var d = document.createElement('div');
      d.id = 'svTyping';
      d.className = 'sv-typing';
      d.innerHTML = '<i></i><i></i><i></i>';
      listEl.appendChild(d);
      listEl.scrollTop = listEl.scrollHeight;
    } else if (!on && t) { t.remove(); }
  }

  // Suggested answers for the outstanding question. Tapping one posts the exact
  // value alongside the label, so the backend stores what the person meant
  // rather than inferring it from prose. Typing instead is always allowed —
  // the chips are an offer, not a gate.
  function chips(key, options) {
    var old = listEl.querySelector('.sv-chips');
    if (old) old.remove();
    if (!key || !options || !options.length) return;
    var box = document.createElement('div');
    box.className = 'sv-chips';
    box.setAttribute('role', 'group');
    box.setAttribute('aria-label', 'Suggested answers');
    options.forEach(function (o) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'sv-chip';
      b.textContent = o.label;
      b.addEventListener('click', function () {
        send(o.label, { signal: key, value: o.value });
      });
      box.appendChild(b);
    });
    listEl.appendChild(box);
    listEl.scrollTop = listEl.scrollHeight;
  }

  function note(text) {
    if (!text || listEl.querySelector('.sv-note')) return;
    var n = document.createElement('div');
    n.className = 'sv-note';
    n.textContent = text;
    listEl.appendChild(n);
  }

  // Survey complete: the recommendation is the payoff, so make it the obvious
  // next move rather than one of three equal-weight buttons.
  function doneState() {
    var acts = root.querySelector('.sv-acts');
    if (!acts || acts.dataset.done === '1') return;
    acts.dataset.done = '1';
    acts.innerHTML =
      '<button class="sv-act" data-act="rec" type="button" ' +
        'style="background:var(--c-moss,#4A5A42);color:#fff;border-color:transparent">' +
        'See how to set up my system</button>' +
      '<button class="sv-act" data-act="refine" type="button">Add more detail</button>';
  }

  function setLive(status) {
    if (!status) return;
    var off = status.live === false;
    statusEl.innerHTML = '<span class="sv-dot"' + (off ? ' data-off="1"' : '') + '></span>' +
                         '<span>' + (off ? 'Limited mode' : 'Online') + '</span>';
    if (off) note(status.note);
  }

  function open() {
    if (!root) build();
    if (!token()) {
      root.hidden = false;
      requestAnimationFrame(function () { root.setAttribute('data-open', '1'); });
      opened = true;
      listEl.innerHTML = '';
      bubble('assistant', 'Please sign in first — Surveyor keeps your profile with your account.');
      inputEl.disabled = sendEl.disabled = true;
      return;
    }
    root.hidden = false;
    requestAnimationFrame(function () { root.setAttribute('data-open', '1'); });
    opened = true;
    document.documentElement.style.overflow = 'hidden';

    if (!listEl.childElementCount) {
      typing(true);
      api('/surveyor/conversation').then(function (r) {
        typing(false);
        if (r.code !== 200) {
          bubble('assistant', r.code === 503
            ? 'Surveyor is unavailable right now. Nothing else on Cordia is affected.'
            : 'Please sign in first — Surveyor keeps your profile with your account.');
          inputEl.disabled = sendEl.disabled = true;
          return;
        }
        (r.data.messages || []).forEach(function (m) { bubble(m.role, m.content, m.created); });
        chips(r.data.key, r.data.options);
        if (r.data.profile && (r.data.profile.percent_complete || 0) >= 100) doneState();
        inputEl.focus();
      });
      api('/surveyor/profile').then(function (r) { setLive(r.data && r.data.llm); });
    } else { inputEl.focus(); }
  }

  function close() {
    if (!root) return;
    root.setAttribute('data-open', '0');
    opened = false;
    document.documentElement.style.overflow = '';
    setTimeout(function () { if (!opened) root.hidden = true; }, 240);
    document.dispatchEvent(new CustomEvent('cordia:surveyor-closed'));
  }

  function send(preset, choice) {
    if (busy) return;
    var text = preset != null ? preset : (inputEl.value || '').trim();
    if (!text) return;
    if (preset == null) { inputEl.value = ''; inputEl.style.height = 'auto'; }
    var old = listEl.querySelector('.sv-chips');
    if (old) old.remove();
    bubble('user', text);
    busy = true;
    sendEl.disabled = true;
    typing(true);

    var payload = { message: text };
    if (choice) payload.choice = choice;

    api('/surveyor/message', payload).then(function (r) {
      typing(false);
      busy = false;
      sendEl.disabled = false;
      if (r.code !== 200 || !r.data.ok) {
        bubble('assistant', r.data && r.data.error
          ? r.data.error
          : 'Something went wrong sending that. Your profile is unchanged — try again.');
        return;
      }
      bubble('assistant', r.data.reply);
      setLive(r.data.llm);
      chips(r.data.key, r.data.options);
      document.dispatchEvent(new CustomEvent('cordia:profile-updated', { detail: r.data.profile }));
      if (r.data.done) doneState();
      inputEl.focus();
    }).catch(function () {
      typing(false); busy = false; sendEl.disabled = false;
      bubble('assistant', 'Connection lost. Your profile is unchanged — try again.');
    });
  }

  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-surveyor]');
    if (t) { e.preventDefault(); open(); }
  });

  window.Cordia = window.Cordia || {};
  window.Cordia.surveyor = { open: open, close: close };
})();
