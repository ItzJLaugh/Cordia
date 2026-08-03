/* Cordia shell — the shared chrome every page gets.

   This codebase has no templating and no build step, so the topbar was
   copy-pasted into ~10 pages and had drifted (one minified, one with a
   different class vocabulary, five with different nav links). Injecting it
   from one place means a change lands everywhere at once.

   Usage: <script src="assets/cordia-shell.js" data-nav="training"></script>
   Renders into #shellHeader if present, else prepends to <body>. */
(function () {
  'use strict';

  var API = location.hostname === 'localhost' ? 'http://127.0.0.1:9995' : '';
  var script = document.currentScript;
  var active = (script && script.dataset.nav) || '';

  // [label, href, nav-key, extra-attributes]
  // Surveyor has no page of its own — it is a modal that opens over wherever
  // you already are, so the link carries data-surveyor and cordia-surveyor.js
  // intercepts the click. surveyor.html exists only as a direct-link fallback.
  // Survey-first. The builder, runtime and agentic pages all still work and are
  // linked from the recommendation, but they are phase-2 scope — leaving them in
  // the top nav made the product read as far larger than the thing we actually
  // want people to do right now, which is answer the survey.
  var NAV = [
    ['Surveyor', 'surveyor.html', 'surveyor', ' data-surveyor'],
    ['Your profile', 'profile.html', 'profile'],
    ['Training', 'training.html', 'training'],
    ['Certifications', 'certifications.html', 'certifications'],
    ['Pricing', 'pricing.html', 'pricing'],
  ];

  var MENU = [
    ['Your space', 'space.html',
      'M24,25 C29,25 33,21 33,16 C33,11 29,7 24,7 C19,7 15,11 15,16 C15,21 19,25 24,25',
      'M9,42 C9,33 15.5,28 24,28 C32.5,28 39,33 39,42'],
    ['Certification', 'certification.html',
      'M24,6 C33.5,6 41.5,14 41.5,23.5 C41.5,33 33.5,41 24,41 C14.5,41 6.5,33 6.5,23.5 C6.5,14 14.5,6 24,6',
      'M16,23 L21.5,28.5 L32,18'],
    ['Assessment', 'assessment.html',
      'M8,40 C8,32 8,24 8,16', 'M18,40 C18,28 18,18 18,10',
      'M28,40 C28,30 28,22 28,20', 'M38,40 C38,26 38,16 38,8'],
    ['Billing', 'pricing.html',
      'M6,13 C18,10 30,10 42,13 C42,22 42,28 42,35 C30,38 18,38 6,35 C6,28 6,22 6,13',
      'M6,20 C18,18 30,18 42,20'],
    ['Workspace', 'interfaces.html',
      'M7,12 C18,9 30,9 41,12 C41,20 41,28 41,36 C30,39 18,39 7,36 C7,28 7,20 7,12',
      'M24,12 C24,20 24,28 24,38'],
    ['Feedback', 'survey.html',
      'M6,11 C18,7.5 30,7.5 42,11 C42,20 42,26 42,32 C33,35 24,35 16,33 C13,36 10,38.5 7,40 C8.5,36.5 9,34 9,32 C7.5,31.6 6.5,31.2 6,31 C6,25 6,18 6,11'],
    ['Sign out', '#signout',
      'M20,8 C14,8 10,12 10,18 C10,24 10,30 10,36 C10,41 14,44 20,44',
      'M24,24 L41,24',
      'M34,17 C36.5,19.3 38.8,21.6 41,24 C38.8,26.4 36.5,28.7 34,31'],
  ];

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function escUrl(p) { return String(p == null ? '' : p).replace(/[^A-Za-z0-9._\/#?=&-]/g, ''); }

  var html =
    '<div class="shell topbar-inner">' +
      '<a class="brand" href="space.html" aria-label="Cordia home">' +
        '<img src="assets/img/cordia-logo-header.webp" alt="Cordia" width="382" height="60">' +
      '</a>' +
      '<nav class="topnav" aria-label="Main">' +
        NAV.map(function (n) {
          return '<a href="' + escUrl(n[1]) + '"' + (n[3] || '') +
            (n[2] === active ? ' class="active" aria-current="page"' : '') +
            '>' + esc(n[0]) + '</a>';
        }).join('') +
      '</nav>' +
      '<div class="acct" id="acct" data-open="0">' +
        '<button class="avatar" id="avatarBtn" type="button" aria-haspopup="true" ' +
          'aria-expanded="false" aria-controls="acctMenu" aria-label="Account menu">' +
          '<span class="initials" id="avatarInitials">&#8734;</span>' +
        '</button>' +
        '<ul class="acct-menu" id="acctMenu" role="menu" aria-label="Account">' +
          MENU.map(function (m) {
            var paths = m.slice(2).map(function (d) { return '<path d="' + d + '"/>'; }).join('');
            return '<li role="none"><a class="acct-item" role="menuitem" href="' + escUrl(m[1]) + '">' +
              '<svg viewBox="0 0 48 48" aria-hidden="true">' + paths + '</svg>' +
              '<span>' + esc(m[0]) + '</span></a></li>';
          }).join('') +
        '</ul>' +
      '</div>' +
    '</div>';

  function mount() {
    var host = document.getElementById('shellHeader');
    if (!host) {
      host = document.createElement('header');
      host.id = 'shellHeader';
      document.body.insertBefore(host, document.body.firstChild);
    }
    host.className = 'topbar';
    host.innerHTML = html;

    var acct = document.getElementById('acct');
    var btn = document.getElementById('avatarBtn');
    var menu = document.getElementById('acctMenu');

    function setOpen(v) {
      acct.dataset.open = v ? '1' : '0';
      btn.setAttribute('aria-expanded', v ? 'true' : 'false');
    }
    btn.addEventListener('click', function (e) { e.stopPropagation(); setOpen(acct.dataset.open !== '1'); });
    document.addEventListener('click', function (e) { if (!acct.contains(e.target)) setOpen(false); });
    addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && acct.dataset.open === '1') { setOpen(false); btn.focus(); }
    });
    menu.addEventListener('click', function (e) {
      var a = e.target.closest('a[href="#signout"]');
      if (!a) return;
      e.preventDefault();
      try { fetch(API + '/auth/logout', { method: 'POST' }).catch(function () {}); } catch (_) {}
      localStorage.removeItem('cordia-token');
      sessionStorage.removeItem('cordia-auth');
      location.replace('index.html');
    });

    // initials from the real session; the mark, not a placeholder, when out
    fetch(API + '/auth/me', {
      headers: { Authorization: 'Bearer ' + (localStorage.getItem('cordia-token') || '') }
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        var slot = document.getElementById('avatarInitials');
        var u = d && d.ok && d.user;
        if (!slot || !u) return;
        var name = (u.name || u.email || '').trim();
        var parts = name.split(/[\s@._-]+/).filter(Boolean);
        slot.textContent = (parts.length > 1 ? parts[0][0] + parts[1][0]
                                             : name.slice(0, 2)).toUpperCase();
      })
      .catch(function () {});
  }

  // Surveyor rides along with the shell so the nav entry works everywhere
  // without editing sixteen pages. Loaded once, guarded against double-include
  // for pages that pull it in directly.
  function loadSurveyor() {
    if (window.Cordia && window.Cordia.surveyor) return;
    if (document.querySelector('script[data-cordia-surveyor]')) return;
    var s = document.createElement('script');
    s.src = 'assets/cordia-surveyor.js';
    s.defer = true;
    s.setAttribute('data-cordia-surveyor', '1');
    document.head.appendChild(s);
  }

  function boot() { mount(); loadSurveyor(); }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
