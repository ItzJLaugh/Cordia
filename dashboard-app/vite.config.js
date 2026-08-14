import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Build-only setup, on purpose. There is no dev-server workflow: the
// backend's CORS allow-list admits only the static origins (:8000/:5500)
// the rest of the site already uses, and this surface must behave like the
// rest of the site — static files under the docroot, served at /dashboard/.
//
// This project lives OUTSIDE web/ deliberately: the production host serves
// the repo's web/ directory as its docroot, so everything under web/ is a
// public URL. Only the build lands there — web/dashboard/ holds nothing
// but index.html and hashed bundles, and the sources, lockfile and this
// config never become fetchable assets. The build output is committed,
// because production serves a git checkout and has no Node toolchain.
// Hashed bundle names make the generated index.html self-cache-busting.
export default defineConfig({
  root: 'src',
  base: '/dashboard/',
  plugins: [react()],
  build: {
    outDir: '../../web/dashboard',
    emptyOutDir: true,
  },
})
