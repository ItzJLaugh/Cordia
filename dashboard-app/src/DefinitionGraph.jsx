import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ReactFlow, Background, Controls, Handle, Position, applyNodeChanges,
} from '@xyflow/react'
import { START_ID, definitionToFlow } from './graph.js'
import StepEdge from './StepEdge.jsx'

// The canvas: a truthful projection of one interface definition, now
// interactive (Step 9). The definition is the single source of truth —
// nodes/edges are always re-derived from it, and every structural edit
// goes up through callbacks to App, which owns the draft. Local node
// state exists ONLY so React Flow can preview a drag; positions are
// ephemeral (the layout is derived — the definition contract has nowhere
// to keep them), and a dragged node's edges drop to the plain fallback
// path because the proven route skeletons are only valid for the derived
// layout.

function StartNode() {
  return (
    <div className="node-start">
      Start
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

function AgentNode({ data, selected }) {
  const cls = ['node-agent']
  if (data.placeholder) cls.push('placeholder')
  if (selected) cls.push('selected')
  const detail = data.detail || 'detailed'
  return (
    <div className={cls.join(' ')}>
      <div className="node-name">{data.name}</div>
      {detail !== 'minimal' && (
        <div className="node-role">{data.placeholder ? 'from an earlier save' : data.role}</div>
      )}
      {detail === 'detailed' && data.instructions && (
        <div className="node-instructions">{data.instructions}</div>
      )}
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

const NODE_TYPES = { cordiaStart: StartNode, cordiaAgent: AgentNode }
const EDGE_TYPES = { cordiaStep: StepEdge }

export default function DefinitionGraph({
  definition, overrides, cardDetail, readOnly, selection,
  onSelect, onConnect, onNodeMoved,
}) {
  const projected = useMemo(
    () => definitionToFlow(definition, overrides,
      { cardDetail, keepStart: !readOnly }),
    [definition, overrides, cardDetail, readOnly],
  )

  // Drag preview only: the projection always wins on the next definition
  // or override change — a stated winner, so server state can never lose
  // to a stale local copy. The selection outline is re-applied here
  // because re-projection replaces the node objects React Flow tracked
  // it on — without this, the outline died on the first keystroke.
  const selectedId = selection && selection.kind === 'agent' ? selection.id : null
  const [nodes, setNodes] = useState(projected.nodes)
  useEffect(() => {
    setNodes(selectedId
      ? projected.nodes.map((n) => (n.id === selectedId ? { ...n, selected: true } : n))
      : projected.nodes)
  }, [projected, selectedId])

  const onNodesChange = useCallback(
    // 'remove' changes are filtered: React Flow's delete gesture would
    // drop the card from local state while the definition (the source of
    // truth) still holds it — canvas and editor would then disagree.
    // Removal has exactly one path, EditorPanel's confirmed Remove.
    (changes) => setNodes((ns) => applyNodeChanges(
      changes.filter((c) => c.type !== 'remove'), ns)),
    [],
  )
  const handleDragStop = useCallback((event, node) => {
    if (node.id !== START_ID && onNodeMoved) onNodeMoved(node.id, node.position)
  }, [onNodeMoved])
  const handleConnect = useCallback((conn) => {
    if (!readOnly && onConnect && conn.source && conn.target
        && conn.target !== START_ID) {
      onConnect(conn.source, conn.target)
    }
  }, [readOnly, onConnect])
  const handleNodeClick = useCallback((event, node) => {
    if (!onSelect) return
    if (node.id === START_ID) { onSelect(null); return }
    onSelect({ kind: 'agent', id: node.id,
               agentIndex: node.data.agentIndex,
               placeholder: Boolean(node.data.placeholder) })
  }, [onSelect])
  const handleEdgeClick = useCallback((event, edge) => {
    if (onSelect && edge.data) onSelect({ kind: 'step', index: edge.data.step })
  }, [onSelect])
  const handlePaneClick = useCallback(() => { if (onSelect) onSelect(null) }, [onSelect])

  if (projected.nodes.length === 0) {
    // With keepStart, an editable canvas always has at least the Start
    // node — this branch is reachable only read-only, where the toolbar
    // is disabled, so the copy must not instruct an unavailable action.
    return (
      <div className="canvas-empty">
        This workspace is a blank canvas so far.
      </div>
    )
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={projected.edges}
      nodeTypes={NODE_TYPES}
      edgeTypes={EDGE_TYPES}
      fitView
      onNodesChange={onNodesChange}
      onNodeDragStop={handleDragStop}
      onConnect={handleConnect}
      onNodeClick={handleNodeClick}
      onEdgeClick={handleEdgeClick}
      onPaneClick={handlePaneClick}
      nodesDraggable={!readOnly}
      nodesConnectable={!readOnly}
      elementsSelectable={!readOnly}
      edgesFocusable={!readOnly}
      deleteKeyCode={null}
      proOptions={{ hideAttribution: false }}
    >
      <Background />
      <Controls showInteractive={false} />
    </ReactFlow>
  )
}
