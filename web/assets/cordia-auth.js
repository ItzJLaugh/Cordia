/* Cordia shared auth gate.
   - Blocks direct navigation to protected pages when no valid session exists.
   - Replaces bare `index.html` links with `/` so the address bar shows the
     canonical root instead of a filename.
   - Add `data-auth-gate` to any page that requires sign-in.
*/
(function () {
  'use strict';
  var API = location.hostname === 'localhost' ? 'http://127.0.0.1:9995' : '';

  function cookie(name) {
    var m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return m ? m[2] : null;
  }

  async function authed() {
    try {
      var r = await fetch(API + '/auth/session', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({token: cookie('cordia_session') || ''}),
        credentials: 'same-origin'
      });
      return r.ok;
    } catch (e) {
      return false;
    }
  }

  function fixLinks() {
    document.querySelectorAll('a[href="index.html"]').forEach(function (a) {
      a.setAttribute('href', '/');
    });
  }

  if (document.body && document.body.hasAttribute('data-auth-gate')) {
    (async function () {
      if (!(await authed())) location.replace('/');
      fixLinks();
    })();
  } else {
    fixLinks();
  }
})();
