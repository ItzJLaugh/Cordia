import { useState } from 'react'
import {
  MAX_INSTRUCTION, MAX_TEXT,
  declareAgent, referencedSteps, removeAgent, removeStep,
  updateAgent, updateStep,
} from './mutations.js'

// The edit surface for whatever is selected on the canvas. Lives BESIDE
// the graph, never inside a node card — the 132px card ceiling is
// load-bearing for the edge-routing clearance proofs, and an inline
// editor would break it. All edits go through the pure mutations module;
// this component only wires fields to them and confirms the destructive
// ones.

function Field({ label, children }) {
  return (
    <label className="ed-field">
      <span className="ed-label">{label}</span>
      {children}
    </label>
  )
}

function AgentEditor({ definition, selection, onChange, onClose }) {
  const [confirming, setConfirming] = useState(false)
  const [hint, setHint] = useState(null)
  const agent = (definition.agents || [])[selection.agentIndex]

  if (selection.placeholder || !agent) {
    return (
      <div className="editor-panel">
        <div className="ed-head">
          <strong>{selection.id}</strong>
          <button type="button" className="ed-close" onClick={onClose}>×</button>
        </div>
        <p className="ed-hint">
          A step references this agent, but the workspace has no record
          for it — likely from an earlier save elsewhere. Declaring it
          makes it editable here; every step keeps pointing at it.
        </p>
        <button
          type="button"
          className="ed-primary"
          onClick={() => {
            const next = declareAgent(definition, selection.id)
            // The new record lands at the end of agents — the selection
            // must say so, or this editor re-renders as a placeholder
            // with a declare button that can no longer do anything.
            if (next) {
              onChange(next, {
                kind: 'agent', id: selection.id,
                agentIndex: next.agents.length - 1, placeholder: false,
              })
            } else {
              // the one refusal declareAgent can hit from here
              setHint('This workspace already holds the maximum 200 agents.')
            }
          }}
        >
          Declare this agent
        </button>
        {hint && <p className="ed-hint">{hint}</p>}
      </div>
    )
  }

  const refs = referencedSteps(definition, agent.id)
  return (
    <div className="editor-panel">
      <div className="ed-head">
        <strong>Agent</strong>
        <button type="button" className="ed-close" onClick={onClose}>×</button>
      </div>
      <Field label="Name">
        <input
          value={agent.name || ''}
          maxLength={MAX_TEXT}
          onChange={(e) => {
            const next = updateAgent(definition, selection.agentIndex, { name: e.target.value })
            if (next) onChange(next, selection)
          }}
        />
      </Field>
      <Field label="Role">
        <input
          value={agent.role || ''}
          maxLength={MAX_TEXT}
          onChange={(e) => {
            const next = updateAgent(definition, selection.agentIndex, { role: e.target.value })
            if (next) onChange(next, selection)
          }}
        />
      </Field>
      <Field label={`Instructions (${(agent.instructions || '').length}/${MAX_INSTRUCTION})`}>
        <textarea
          rows={6}
          value={agent.instructions || ''}
          maxLength={MAX_INSTRUCTION}
          onChange={(e) => {
            const next = updateAgent(definition, selection.agentIndex, { instructions: e.target.value })
            if (next) onChange(next, selection)
          }}
        />
      </Field>
      {confirming ? (
        <div className="ed-confirm">
          {refs === 1
            ? 'Removing this agent also removes the step that runs on it.'
            : refs > 1
              ? `Removing this agent also removes the ${refs} steps that run on it.`
              : 'Remove this agent from the workspace?'}
          <div className="ed-confirm-row">
            <button
              type="button"
              className="ed-danger"
              onClick={() => onChange(removeAgent(definition, agent.id), null)}
            >
              Remove
            </button>
            <button type="button" onClick={() => setConfirming(false)}>Keep it</button>
          </div>
        </div>
      ) : (
        <button type="button" className="ed-danger" onClick={() => setConfirming(true)}>
          Remove agent…
        </button>
      )}
    </div>
  )
}

function StepEditor({ definition, selection, onChange, onClose }) {
  const [confirming, setConfirming] = useState(false)
  const steps = ((definition.workflow || {}).steps) || []
  const step = steps[selection.index]
  if (!step) return null
  const tools = (definition.tools || []).filter((t) => t && typeof t.id === 'string')
  const agentName = (() => {
    const a = (definition.agents || []).find((x) => x && x.id === step.agentId)
    return (a && a.name) || step.agentId
  })()

  return (
    <div className="editor-panel">
      <div className="ed-head">
        <strong>Step {selection.index + 1} — {agentName}</strong>
        <button type="button" className="ed-close" onClick={onClose}>×</button>
      </div>
      <Field label={`Instruction (${(step.instruction || '').length}/${MAX_INSTRUCTION})`}>
        <textarea
          rows={4}
          value={step.instruction || ''}
          maxLength={MAX_INSTRUCTION}
          onChange={(e) => {
            const next = updateStep(definition, selection.index, { instruction: e.target.value })
            if (next) onChange(next, selection)
          }}
        />
      </Field>
      <label className="ed-check">
        <input
          type="checkbox"
          checked={Boolean(step.requiresApproval)}
          onChange={(e) => {
            const next = updateStep(definition, selection.index, { requiresApproval: e.target.checked })
            if (next) onChange(next, selection)
          }}
        />
        Pause for your approval before this step's work is used
      </label>
      {tools.length > 0 && (
        <Field label="Tools this step may use">
          <div className="ed-tools">
            {tools.map((t) => {
              const on = (step.toolIds || []).includes(t.id)
              return (
                <label key={t.id} className="ed-check">
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => {
                      const ids = on
                        ? (step.toolIds || []).filter((x) => x !== t.id)
                        : [...(step.toolIds || []), t.id]
                      const next = updateStep(definition, selection.index, { toolIds: ids })
                      if (next) onChange(next, selection)
                    }}
                  />
                  {t.name || t.id}
                </label>
              )
            })}
          </div>
        </Field>
      )}
      {confirming ? (
        <div className="ed-confirm">
          Removing this step relinks the flow around it.
          <div className="ed-confirm-row">
            <button
              type="button"
              className="ed-danger"
              onClick={() => {
                const next = removeStep(definition, selection.index)
                if (next) onChange(next, null)
              }}
            >
              Remove
            </button>
            <button type="button" onClick={() => setConfirming(false)}>Keep it</button>
          </div>
        </div>
      ) : (
        <button type="button" className="ed-danger" onClick={() => setConfirming(true)}>
          Remove step…
        </button>
      )}
    </div>
  )
}

export default function EditorPanel({ definition, selection, onChange, onClose }) {
  if (!selection || !definition) return null
  // Keyed by selection identity: an armed destructive confirmation must
  // die with the selection that armed it — component-position reuse let
  // one click delete something the person never confirmed.
  if (selection.kind === 'agent') {
    return (
      <AgentEditor
        key={`agent-${selection.id}`}
        definition={definition} selection={selection}
        onChange={onChange} onClose={onClose}
      />
    )
  }
  if (selection.kind === 'step') {
    // Identity, not position: after an insert or delete a DIFFERENT step
    // can land on the same index, and an index key would carry an armed
    // delete confirmation onto it. Step ids exist on everything this
    // surface mints; legacy id-less steps fall back to the index.
    const step = (((definition.workflow || {}).steps) || [])[selection.index]
    const stepKey = (step && typeof step.id === 'string' && step.id)
      ? `step-${step.id}` : `stepidx-${selection.index}`
    return (
      <StepEditor
        key={stepKey}
        definition={definition} selection={selection}
        onChange={onChange} onClose={onClose}
      />
    )
  }
  return null
}
