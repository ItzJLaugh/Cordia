import React from 'react'

export default function ArtifactItems({ items }) {
  if (!Array.isArray(items) || items.length === 0) return null
  return React.createElement('ul', { className: 'artifact-items' }, items.map((item, index) => (
    React.createElement('li', { key: `${item.label}:${index}` },
      React.createElement('span', { className: 'artifact-item-main' },
        React.createElement('span', null, item.label),
        item.detail ? React.createElement('span', { className: 'artifact-item-detail' }, item.detail) : null,
      ),
      item.meta ? React.createElement('span', { className: 'artifact-meta' }, item.meta) : null,
    )
  )))
}
