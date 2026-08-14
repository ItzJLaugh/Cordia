const API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  ? 'http://127.0.0.1:9995'
  : ''

function safeServerError(value) {
  return typeof value === 'string'
    && value.length <= 160
    && /^[A-Za-z0-9][A-Za-z0-9 .,'!?-]*$/.test(value)
    ? value
    : 'Request failed'
}

// GET is the only Alidora client operation. The HttpOnly session cookie stays
// in the browser; a manually supplied local-development token remains useful
// for the documented cross-origin development setup.
export async function getApi(path) {
  const headers = {}
  const devToken = localStorage.getItem('cordia-dev-token')
  if (devToken) headers.Authorization = `Bearer ${devToken}`

  const response = await fetch(API + path, {
    method: 'GET',
    headers,
    credentials: 'include',
  })
  const body = await response.json().catch(() => null)
  if (!response.ok || !body || body.ok !== true) {
    throw new Error(safeServerError(body && body.error))
  }
  return body
}
