import React from 'react'

const GITHUB_REPOSITORY_LINK = {
  href: '/github.html',
  label: 'Open GitHub repositories',
}

export default function ArtifactLink({ link }) {
  if (!link || typeof link !== 'object' || Array.isArray(link)
      || Object.keys(link).sort().join('|') !== 'href|label'
      || link.href !== GITHUB_REPOSITORY_LINK.href
      || link.label !== GITHUB_REPOSITORY_LINK.label) return null
  return React.createElement('a', {
    className: 'artifact-link',
    href: GITHUB_REPOSITORY_LINK.href,
  }, GITHUB_REPOSITORY_LINK.label)
}
