import { createHash } from 'node:crypto'
import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const projectRoot = fileURLToPath(new URL('.', import.meta.url))
const outputRoot = fileURLToPath(new URL('../web/dashboard/', import.meta.url))

function filesBelow(directory, base = directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolute = join(directory, entry.name)
    if (entry.isDirectory()) return filesBelow(absolute, base)
    return entry.isFile() ? [relative(base, absolute).replaceAll('\\', '/')] : []
  })
}

function sha256(value) {
  return createHash('sha256').update(value).digest('hex')
}

function canonicalSource(relativePath) {
  return readFileSync(join(projectRoot, relativePath), 'utf8').replace(/\r\n?/g, '\n')
}

function sourceHash(files) {
  const aggregate = createHash('sha256')
  for (const file of files) {
    aggregate.update(`${file}\n${sha256(canonicalSource(file))}\n`, 'utf8')
  }
  return aggregate.digest('hex')
}

function buildProvenance() {
  return {
    name: 'cordia-build-provenance',
    apply: 'build',
    closeBundle() {
      const sourceFiles = [
        'package-lock.json',
        'package.json',
        ...filesBelow(join(projectRoot, 'src')).map((file) => `src/${file}`),
        'vite.config.js',
      ].sort()
      const outputFiles = filesBelow(outputRoot)
        .filter((file) => file === 'index.html' || /^assets\/index-[A-Za-z0-9_-]+\.(?:css|js)$/.test(file))
        .sort()
      const manifest = {
        schema: 1,
        algorithm: 'sha256',
        source: {
          normalization: 'lf',
          files: sourceFiles,
          sha256: sourceHash(sourceFiles),
        },
        outputs: outputFiles.map((file) => ({
          path: file,
          sha256: sha256(readFileSync(join(outputRoot, file))),
        })),
      }
      writeFileSync(
        join(outputRoot, 'build-provenance.json'),
        `${JSON.stringify(manifest, null, 2)}\n`,
        'utf8',
      )
    },
  }
}

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
  plugins: [react(), buildProvenance()],
  build: {
    outDir: '../../web/dashboard',
    emptyOutDir: true,
  },
})
