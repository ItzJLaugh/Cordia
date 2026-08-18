import React, { useRef, useState } from 'react'

const KEY_TARGET = {
  ArrowLeft: -1,
  ArrowRight: 1,
}

export default function InspectionDock({ model }) {
  const tabs = model && Array.isArray(model.tabs) ? model.tabs : []
  const [activeId, setActiveId] = useState(tabs[0] ? tabs[0].id : '')
  const buttonRefs = useRef([])
  const activeIndex = Math.max(0, tabs.findIndex((tab) => tab.id === activeId))
  const active = tabs[activeIndex]

  function select(index) {
    if (!tabs.length) return
    const next = (index + tabs.length) % tabs.length
    setActiveId(tabs[next].id)
    buttonRefs.current[next]?.focus()
  }

  function onTabKeyDown(event, index) {
    if (Object.hasOwn(KEY_TARGET, event.key)) {
      event.preventDefault()
      select(index + KEY_TARGET[event.key])
    } else if (event.key === 'Home') {
      event.preventDefault()
      select(0)
    } else if (event.key === 'End') {
      event.preventDefault()
      select(tabs.length - 1)
    }
  }

  if (!active) return null

  const tabButtons = tabs.map((tab, index) => {
    const selected = tab.id === active.id
    return React.createElement('button', {
      key: tab.id,
      ref: (node) => { buttonRefs.current[index] = node },
      id: `inspection-tab-${tab.id}`,
      type: 'button',
      role: 'tab',
      'aria-selected': selected,
      'aria-controls': `inspection-panel-${tab.id}`,
      tabIndex: selected ? 0 : -1,
      onClick: () => setActiveId(tab.id),
      onKeyDown: (event) => onTabKeyDown(event, index),
    }, tab.label)
  })

  const panelContent = active.rows.length
    ? React.createElement('ul', { className: 'inspection-rows' }, active.rows.map((row) => (
      React.createElement('li', { key: row.id },
        React.createElement('div', { className: 'inspection-row-main' },
          React.createElement('span', { className: 'inspection-row-label' }, row.label),
          row.detail && React.createElement('span', { className: 'inspection-row-detail' }, row.detail),
        ),
        row.status && React.createElement('span', { className: 'inspection-row-status' }, row.status),
      )
    )))
    : React.createElement('p', { className: 'inspection-empty' }, active.empty)

  return React.createElement('section', { className: 'inspection-dock', 'aria-labelledby': 'inspection-heading' },
    React.createElement('header', { className: 'inspection-heading' },
      React.createElement('div', null,
        React.createElement('span', { className: 'eyebrow' }, 'Workspace details'),
        React.createElement('h2', { id: 'inspection-heading' }, 'Inspection dock'),
      ),
      React.createElement('span', { className: 'inspection-mode' }, 'Read-only'),
    ),
    React.createElement('div', { className: 'inspection-tabs', role: 'tablist', 'aria-label': 'Workspace inspection' }, tabButtons),
    React.createElement('div', {
      className: 'inspection-panel',
      id: `inspection-panel-${active.id}`,
      role: 'tabpanel',
      'aria-labelledby': `inspection-tab-${active.id}`,
      tabIndex: 0,
    }, panelContent),
  )
}
