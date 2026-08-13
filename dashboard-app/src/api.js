// The dashboard's one seam to the backend, matching the house convention
// (interface.html et al.): same-origin in production behind Apache, the
// explicit local port in dev, responses resolved to {code, data} so callers
// branch on status without try/catch.
//
// The session is the HttpOnly cookie the browser sends automatically —
// this file never sees a token. The one exception: a Bearer header from
// localStorage['cordia-dev-token'], which nothing in the product ever
// writes. It exists because local dev is cross-origin (:8000 static,
// :9995 API) where the cookie cannot travel; setting the token by hand in
// devtools is the same header path the backend documents for CLI callers.
const API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  ? 'http://127.0.0.1:9995'
  : ''

export function api(path, body) {
  const headers = { 'Content-Type': 'application/json' }
  const devToken = localStorage.getItem('cordia-dev-token')
  if (devToken) headers.Authorization = 'Bearer ' + devToken
  return fetch(API + path, {
    method: body ? 'POST' : 'GET',
    headers,
    credentials: 'same-origin',
    body: body ? JSON.stringify(body) : undefined,
  }).then((r) =>
    r.json().catch(() => ({})).then((data) => ({ code: r.status, data })),
  )
}
