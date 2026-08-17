import React, { useRef, useState } from 'react'

import { postLogout } from './api.js'

const FAILURE_MESSAGE = 'Cordia could not sign you out. Try again.'

function clearBrowserAuthHints() {
  try { localStorage.removeItem('cordia-dev-token') } catch (_) {}
  try { sessionStorage.removeItem('cordia-auth') } catch (_) {}
}

export default function SignOutControl() {
  const operation = useRef(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  async function signOut() {
    if (operation.current) return false
    operation.current = true
    setPending(true)
    setError('')

    try {
      await postLogout()
    } catch (_) {
      operation.current = false
      setPending(false)
      setError(FAILURE_MESSAGE)
      return false
    }

    clearBrowserAuthHints()
    window.location.replace('/')
    return true
  }

  return React.createElement(
    'div',
    { className: 'signout-control' },
    React.createElement(
      'button',
      {
        type: 'button',
        disabled: pending,
        'aria-busy': pending,
        onClick: signOut,
      },
      pending ? 'Signing out…' : 'Sign out',
    ),
    error ? React.createElement('span', { role: 'alert' }, error) : null,
  )
}
