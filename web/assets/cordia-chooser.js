/* Cordia chooser — certifications, cognitive categories, search, detail view.

   Search is entirely client-side over the 78 catalogue entities already in
   memory (3 tiers + 15 tracks + 60 courses). No network call, so it cannot
   be slow, cannot fail, and cannot serialise behind the single-threaded
   backend. Typing renders synchronously in one frame.

   Access rule matches cordia_paywall.entitled(): '*' wildcard, then
   free_tracks, then an exact entitlement row. */
(function () {
  'use strict';

  var API = location.hostname === 'localhost' ? 'http://127.0.0.1:9995' : '';
  var BADGE = { aie: 'assets/img/badge-aie.svg',
                caie: 'assets/img/badge-caie.svg',
                caaie: 'assets/img/badge-caaie.svg' };

  var tracks = (typeof TRACKS !== 'undefined' && TRACKS) || [];
  var tiers  = (typeof TIERS  !== 'undefined' && TIERS)  || [];
  var cats   = (typeof CATEGORIES !== 'undefined' && CATEGORIES) || [];
  var icons  = (typeof ICONS !== 'undefined' && ICONS) || {};

  var ACCESS = null, accessKnown = false;
  var q = '', state = 'idle', lastFocus = null;

  var el = {
    certRow:  document.getElementById('certRow'),
    catalogue:document.getElementById('catalogue'),
    results:  document.getElementById('results'),
    resultGrid: document.getElementById('resultGrid'),
    empty:    document.getElementById('resultsEmpty'),
    input:    document.getElementById('q'),
    status:   document.getElementById('qStatus'),
    detail:   document.getElementById('detail'),
    sheet:    document.getElementById('sheet'),
    finder:   document.getElementById('finder'),
  };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  // background-image / href go into a CSS or URL context, where esc() is the
  // wrong escaper — strip anything that isn't a safe path character instead
  function escUrl(p) { return String(p == null ? '' : p).replace(/[^A-Za-z0-9._\/-]/g, ''); }

  var byId = {};
  tracks.forEach(function (t) { byId[t.id] = t; });

  /* ---------------- access ---------------- */
  function unlocked(t) {
    if (!ACCESS) return false;
    var ents = ACCESS.entitlements || [];
    for (var i = 0; i < ents.length; i++) if (ents[i].track === '*') return true;
    if ((ACCESS.free_tracks || []).indexOf(t.id) > -1) return true;
    for (var j = 0; j < ents.length; j++) if (ents[j].track === t.id) return true;
    return false;
  }

  /* ---------------- search index ---------------- */
  var norm = function (s) {
    return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  };
  var tokens = function (s) { return norm(s).split(/[^a-z0-9]+/).filter(Boolean); };

  var index = [];   // {kind:'track'|'tier', ref, fields:[{text,weight}]}
  tracks.forEach(function (t) {
    var catName = '';
    cats.forEach(function (c) { if (c.tracks.indexOf(t.id) > -1) catName = c.name; });
    index.push({ kind: 'track', ref: t, fields: [
      { text: t.name, w: 10 }, { text: t.id, w: 8 },
      { text: (t.env && t.env.title) || '', w: 5 },
      { text: (t.courses || []).join(' '), w: 4 },
      { text: catName, w: 4 },
      { text: t.cog || '', w: 3 }, { text: t.fail || '', w: 2 },
      { text: (t.env && t.env.setup) || '', w: 2 },
    ]});
  });
  tiers.forEach(function (t) {
    index.push({ kind: 'tier', ref: t, fields: [
      { text: t.code, w: 10 }, { text: t.name, w: 10 },
      { text: (t.courses || []).map(function (c) { return c.t || c.name || ''; }).join(' '), w: 4 },
      { text: t.claim || '', w: 3 }, { text: t.who || '', w: 3 },
    ]});
  });
  index.forEach(function (e) {
    e.toks = e.fields.map(function (f) { return { set: tokens(f.text), w: f.w }; });
  });

  // Damerau-Levenshtein, capped — only used when nothing better matched
  function edits(a, b, max) {
    if (Math.abs(a.length - b.length) > max) return max + 1;
    var prev = [], cur = [], i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      cur[0] = i; var best = cur[0];
      for (j = 1; j <= b.length; j++) {
        var cost = a[i - 1] === b[j - 1] ? 0 : 1;
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
        if (cur[j] < best) best = cur[j];
      }
      if (best > max) return max + 1;
      prev = cur.slice();
    }
    return prev[b.length];
  }

  function quality(qt, ft) {
    if (ft === qt) return 1.0;
    if (ft.indexOf(qt) === 0) return 0.80;
    if (ft.indexOf(qt) > -1) return 0.60;
    if (qt.length >= 4) {
      var max = qt.length >= 7 ? 2 : 1;
      if (edits(qt, ft, max) <= max) return 0.45;
    }
    return 0;
  }

  function search(str) {
    var qts = tokens(str);
    if (!qts.length) return [];
    var out = [];
    index.forEach(function (e) {
      var total = 0, hitFields = 0, allHit = true;
      for (var qi = 0; qi < qts.length; qi++) {
        var bestForToken = 0;
        for (var fi = 0; fi < e.toks.length; fi++) {
          var f = e.toks[fi], bq = 0;
          for (var ti = 0; ti < f.set.length; ti++) {
            var qy = quality(qts[qi], f.set[ti]);
            if (qy > bq) bq = qy;
            if (bq === 1) break;
          }
          if (bq > 0) { hitFields++; if (bq * f.w > bestForToken) bestForToken = bq * f.w; }
        }
        if (bestForToken === 0) { allHit = false; break; }
        total += bestForToken;
      }
      if (allHit) out.push({ e: e, score: total + 0.15 * hitFields });
    });
    out.sort(function (a, b) { return b.score - a.score; });
    return out.map(function (o) { return o.e; });
  }

  /* ---------------- rendering ---------------- */
  function certCard(t) {
    return '<li><a class="cert" href="exam.html?cert=' + escUrl(t.id) + '">' +
      '<img class="cert-badge" src="' + escUrl(BADGE[t.id] || '') + '" alt="" width="140" height="140">' +
      '<span class="cert-code">' + esc(t.code) + '</span>' +
      '<span class="cert-name">' + esc(t.name) + '</span></a></li>';
  }

  function iconSvg(name) {
    var i = icons[name];
    if (!i) return '';
    return '<svg viewBox="0 0 48 48" aria-hidden="true">' +
      i.d.map(function (d) { return '<path d="' + d + '"/>'; }).join('') + '</svg>';
  }

  function winCard(t) {
    var open = unlocked(t);
    var n = String(t.n == null ? '' : t.n).padStart(2, '0');
    var envTitle = (t.env && t.env.title) || '';
    return '<li class="win' + (accessKnown && !open ? ' locked' : '') + '">' +
      '<button class="win-hit" type="button" data-id="' + esc(t.id) + '">' +
        '<span class="win-eyebrow">' + n + ' &middot; ' + esc(t.id) + '</span>' +
        '<span class="win-title">' + esc(t.name) + '</span>' +
        // Two course titles, then a count. Listing all four put ~38 words on
        // every card, and fifteen of those made the catalogue a wall of text
        // to scan rather than a set of things to choose between. The full list
        // is one tap away in the detail sheet.
        '<ul class="win-obj">' + (t.courses || []).slice(0, 2).map(function (c) {
          return '<li>' + esc(typeof c === 'string' ? c : (c.t || c.name || '')) + '</li>';
        }).join('') +
        ((t.courses || []).length > 2
          ? '<li class="win-more">+' + ((t.courses || []).length - 2) + ' more</li>'
          : '') + '</ul>' +
        '<span class="win-foot"><span>' +
          (accessKnown ? (open ? 'Open' : '$79') : 'View') + '</span>' +
          (envTitle ? '<span class="win-env">' + esc(envTitle) + '</span>' : '') +
          '<span class="win-go" aria-hidden="true">&rarr;</span></span>' +
      '</button></li>';
  }

  function tierResultCard(t) {
    return '<li class="win"><button class="win-hit" type="button" data-tier="' + esc(t.id) + '">' +
      '<span class="win-eyebrow">Certification</span>' +
      '<span class="win-title">' + esc(t.code) + '</span>' +
      '<ul class="win-obj">' + (t.courses || []).slice(0, 4).map(function (c) {
        return '<li>' + esc(c.t || c.name || '') + '</li>';
      }).join('') + '</ul>' +
      '<span class="win-foot"><span>' + esc(t.name) + '</span>' +
      '<span class="win-go" aria-hidden="true">&rarr;</span></span>' +
      '</button></li>';
  }

  function renderCatalogue() {
    el.catalogue.innerHTML = cats.map(function (c) {
      var items = c.tracks.map(function (id) { return byId[id]; }).filter(Boolean);
      return '<section class="cat" aria-labelledby="cat-' + esc(c.id) + '">' +
        '<div class="cat-head">' +
          '<h2 class="cat-h" id="cat-' + esc(c.id) + '">' + esc(c.name) + '</h2>' +
          '<p class="cat-sub">' + esc(c.sub) + '</p>' +
          '<ul class="cat-icons" role="list">' + c.icons.map(function (n) {
            return '<li>' + iconSvg(n) + '<span>' + esc((icons[n] || {}).t || '') + '</span></li>';
          }).join('') + '</ul>' +
        '</div>' +
        '<ol class="win-grid" role="list">' + items.map(winCard).join('') + '</ol>' +
      '</section>';
    }).join('');
  }

  function renderResults() {
    var hits = search(q);
    el.resultGrid.innerHTML = hits.map(function (e) {
      return e.kind === 'tier' ? tierResultCard(e.ref) : winCard(e.ref);
    }).join('');
    var n = hits.length;
    if (n === 0) {
      // never a dead end: offer the three closest tracks by single-token match
      var near = index.filter(function (e) { return e.kind === 'track'; }).slice(0, 3);
      el.empty.innerHTML = 'No tracks match &ldquo;' + esc(q.trim()) + '&rdquo;. Try one of these:' +
        '<ol class="win-grid" role="list" style="margin-top:22px">' +
        near.map(function (e) { return winCard(e.ref); }).join('') + '</ol>';
      el.empty.hidden = false;
    } else {
      el.empty.hidden = true;
    }
    el.status.textContent = n + (n === 1 ? ' result' : ' results') +
      ' for ' + q.trim();
  }

  function apply() {
    var len = q.trim().length;
    state = len === 0 ? 'idle' : (len < 2 ? 'typing' : 'results');
    var showResults = state === 'results';
    el.results.hidden = !showResults;
    el.catalogue.hidden = showResults;
    el.input.setAttribute('aria-expanded', showResults ? 'true' : 'false');
    if (showResults) renderResults();
    else el.status.textContent = '';
  }

  /* ---------------- detail view ---------------- */
  function blk(h, body, cls) {
    if (!body) return '';
    return '<div class="blk' + (cls ? ' ' + cls : '') + '"><h3>' + esc(h) + '</h3>' +
      '<p>' + esc(body) + '</p></div>';
  }

  function openTrack(id) {
    var t = byId[id];
    if (!t) return;
    var open = unlocked(t);
    var n = String(t.n == null ? '' : t.n).padStart(2, '0');
    var courseName = (t.courses && t.courses[0]) || '';
    if (typeof courseName !== 'string') courseName = courseName.t || courseName.name || '';
    show(
      '<button class="x" data-close type="button" aria-label="Close">&times;</button>' +
      '<div class="sheet-bd">' +
        '<p class="eyebrow">Track ' + n + (t.env && t.env.title ? ' &middot; ' + esc(t.env.title) : '') + '</p>' +
        '<h2 id="sheetTitle" class="sheet-title">' + esc(t.name) + '</h2>' +
        '<div class="blk"><h3>Objectives</h3><ul class="win-obj">' +
          (t.courses || []).map(function (c) {
            return '<li>' + esc(typeof c === 'string' ? c : (c.t || '')) + '</li>';
          }).join('') + '</ul></div>' +
        blk('What it measures', t.cog) +
        blk('The failure it trains out of you', t.fail, 'fail') +
        blk('How it is scored', t.evalnote) +
        (t.env ? '<div class="hair"></div>' +
          blk('The environment — ' + (t.env.title || ''), t.env.setup) +
          blk('Your first instruction', t.env.promptA) : '') +
        '<div class="acts">' +
          (open
            ? '<a class="btn" href="course.html?track=' + escUrl(t.id) +
                '&course=' + encodeURIComponent(courseName) + '">Enter track</a>'
            : '<a class="btn" href="pricing.html">Unlock &mdash; $79</a>') +
          '<a class="btn btn-quiet" href="certification.html">View certification</a>' +
        '</div>' +
      '</div>');
  }

  function openTier(id) {
    var t = null;
    tiers.forEach(function (x) { if (x.id === id) t = x; });
    if (!t) return;
    show(
      '<button class="x" data-close type="button" aria-label="Close">&times;</button>' +
      '<div class="sheet-bd">' +
        '<p class="eyebrow">Certification tier</p>' +
        '<h2 id="sheetTitle" class="sheet-title">' + esc(t.code) + '</h2>' +
        '<div class="blk"><h3>Courses</h3><ul class="win-obj">' +
          (t.courses || []).map(function (c) {
            return '<li>' + esc(c.t || c.name || '') +
              (c.m ? '<em>' + esc(c.m) + '</em>' : '') + '</li>';
          }).join('') + '</ul></div>' +
        blk('What it certifies', t.claim || t.who) +
        blk('Item signature', t.signature) +
        blk('Where the cut sits', t.cut) +
        blk('Item mix', t.mix) +
        '<div class="acts">' +
          '<a class="btn" href="tier.html?tier=' + escUrl(t.id) + '">Open ' + esc(t.code) + '</a>' +
          '<a class="btn btn-quiet" href="pricing.html">See pricing</a>' +
        '</div>' +
      '</div>');
  }

  function show(html) {
    el.sheet.innerHTML = html;
    lastFocus = document.activeElement;
    el.detail.classList.add('on');
    document.body.style.overflow = 'hidden';
    var c = el.sheet.querySelector('.x');
    if (c) c.focus();
  }

  function close() {
    el.detail.classList.remove('on');
    document.body.style.overflow = '';
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  // focus trap — a modal that lets focus escape behind the scrim is a
  // keyboard dead end
  el.detail.addEventListener('keydown', function (e) {
    if (e.key !== 'Tab') return;
    var f = el.sheet.querySelectorAll('a[href],button:not([disabled])');
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

  /* ---------------- events ---------------- */
  function onGridClick(e) {
    var b = e.target.closest('.win-hit');
    if (!b) return;
    // A domain is a COURSE, so it navigates to its own page (objectives,
    // prerequisites, environment) rather than opening a modal preview.
    if (b.dataset.tier) openTier(b.dataset.tier);
    else if (b.dataset.id) location.href = 'domain.html?track=' + escUrl(b.dataset.id);
  }
  el.catalogue.addEventListener('click', onGridClick);
  el.results.addEventListener('click', onGridClick);
  el.detail.addEventListener('click', function (e) {
    if (e.target.closest('[data-close]')) close();
  });

  el.input.addEventListener('input', function () { q = el.input.value; apply(); });
  addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      if (el.detail.classList.contains('on')) { close(); return; }
      if (document.activeElement === el.input && q) { el.input.value = ''; q = ''; apply(); }
      return;
    }
    if (e.key === '/' && document.activeElement !== el.input && !el.detail.classList.contains('on')) {
      e.preventDefault(); el.input.focus(); el.input.select();
    }
  });

  /* proximity sheen — ONE delegated listener, rAF-throttled, will-change
     released on leave so we never hold 18 promoted layers */
  function attachSheen(root) {
    var pending = false, ev = null;
    root.addEventListener('pointermove', function (e) {
      ev = e;
      if (pending) return;
      pending = true;
      requestAnimationFrame(function () {
        pending = false;
        var t = ev.target.closest ? ev.target.closest('.win-hit,.cert') : null;
        if (!t) return;
        var r = t.getBoundingClientRect();
        if (!r.width || !r.height) return;
        t.style.setProperty('--px', ((ev.clientX - r.left) / r.width).toFixed(3));
        t.style.setProperty('--py', ((ev.clientY - r.top) / r.height).toFixed(3));
      });
    }, { passive: true });
    root.addEventListener('pointerover', function (e) {
      var t = e.target.closest ? e.target.closest('.win-hit,.cert') : null;
      if (t) t.style.willChange = 'transform';
    });
    root.addEventListener('pointerout', function (e) {
      var t = e.target.closest ? e.target.closest('.win-hit,.cert') : null;
      if (t) t.style.willChange = '';
    });
  }

  /* ---------------- account menu ---------------- */
  var MENU = [
    ['Profile',   'profile.html',        'M24,25 C29,25 33,21 33,16 C33,11 29,7 24,7 C19,7 15,11 15,16 C15,21 19,25 24,25', 'M9,42 C9,33 15.5,28 24,28 C32.5,28 39,33 39,42'],
    ['Account',   'profile.html',        'M8,14 C18,10 30,10 40,14 C40,24 40,31 24,41 C8,31 8,24 8,14', 'M17,24 L22,29 L32,19'],
    ['Billing',   'pricing.html',      'M6,13 C18,10 30,10 42,13 C42,22 42,28 42,35 C30,38 18,38 6,35 C6,28 6,22 6,13', 'M6,20 C18,18 30,18 42,20'],
    ['Certification', 'certification.html', 'M24,6 C33.5,6 41.5,14 41.5,23.5 C41.5,33 33.5,41 24,41 C14.5,41 6.5,33 6.5,23.5 C6.5,14 14.5,6 24,6', 'M16,23 L21.5,28.5 L32,18'],
    ['Feedback',  'certification.html',       'M6,11 C18,7.5 30,7.5 42,11 C42,20 42,26 42,32 C33,35 24,35 16,33 C13,36 10,38.5 7,40 C8.5,36.5 9,34 9,32 C7.5,31.6 6.5,31.2 6,31 C6,25 6,18 6,11'],
    ['Assessment','assessment.html',   'M8,40 C8,32 8,24 8,16', 'M18,40 C18,28 18,18 18,10', 'M28,40 C28,30 28,22 28,20', 'M38,40 C38,26 38,16 38,8'],
    ['Sign out',  '#signout',          'M20,8 C14,8 10,12 10,18 C10,24 10,30 10,36 C10,41 14,44 20,44', 'M24,24 L41,24', 'M34,17 C36.5,19.3 38.8,21.6 41,24 C38.8,26.4 36.5,28.7 34,31'],
  ];

  function initAccount() {
    var acct = document.getElementById('acct');
    var btn = document.getElementById('avatarBtn');
    var menu = document.getElementById('acctMenu');
    if (!acct || !btn || !menu) return;
    menu.innerHTML = MENU.map(function (m) {
      var paths = m.slice(2).map(function (d) { return '<path d="' + d + '"/>'; }).join('');
      return '<li role="none"><a class="acct-item" role="menuitem" href="' + escUrl(m[1]) + '">' +
        '<svg viewBox="0 0 48 48" aria-hidden="true">' + paths + '</svg>' +
        '<span>' + esc(m[0]) + '</span></a></li>';
    }).join('');
    function setOpen(v) {
      acct.dataset.open = v ? '1' : '0';
      btn.setAttribute('aria-expanded', v ? 'true' : 'false');
    }
    btn.addEventListener('click', function (e) {
      e.stopPropagation(); setOpen(acct.dataset.open !== '1');
    });
    document.addEventListener('click', function (e) {
      if (!acct.contains(e.target)) setOpen(false);
    });
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
  }

  /* ---------------- boot ---------------- */
  renderCatalogue();
  attachSheen(el.catalogue);
  attachSheen(el.results);
  if (el.certRow) {
    el.certRow.innerHTML = tiers.map(certCard).join('');
    attachSheen(el.certRow);
  }
  // account menu is provided by cordia-shell.js
  apply();

  fetch(API + '/pay/my-access', {
    headers: { Authorization: 'Bearer ' + (localStorage.getItem('cordia-token') || '') }
  })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) { if (d && d.ok) ACCESS = d; })
    .catch(function () {})
    .finally(function () {
      accessKnown = !!ACCESS;
      renderCatalogue();
      if (state === 'results') renderResults();
    });

  // avatar initials from the signed-in account; falls back to the mark rather
  // than showing a placeholder dash to a signed-out visitor
  (function () {
    var slot = document.getElementById('avatarInitials');
    if (!slot) return;
    fetch(API + '/auth/me', {
      headers: { Authorization: 'Bearer ' + (localStorage.getItem('cordia-token') || '') }
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        var u = d && d.ok && d.user;
        if (!u) { slot.textContent = '∞'; return; }
        var name = (u.name || u.email || '').trim();
        var parts = name.split(/[\s@._-]+/).filter(Boolean);
        slot.textContent = (parts.length > 1
          ? parts[0][0] + parts[1][0]
          : name.slice(0, 2)).toUpperCase();
      })
      .catch(function () { slot.textContent = '∞'; });
  })();
})();
