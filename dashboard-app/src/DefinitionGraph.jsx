import { useMemo } from 'react'
import { Background, Controls, Handle, Position, ReactFlow } from '@xyflow/react'

import { alidoraMapToFlow } from './graph.js'

function AlidoraNode({ data }) {
  return (
    <div className="node-agent">
      <div className="node-name">{data.label || data.kind || 'System artifact'}</div>
      {data.kind && <div className="node-role">{data.kind}</div>}
      {data.detail && <div className="node-instructions">{data.detail}</div>}
      {data.connectorStatus && (
        <dl className="node-status" aria-label="Connector status">
          <div><dt>Consent</dt><dd>{data.connectorStatus.consent}</dd></div>
          <div><dt>Adapter</dt><dd>{data.connectorStatus.implementation}</dd></div>
          <div><dt>Lifecycle</dt><dd>{data.connectorStatus.lifecycle.replaceAll('_', ' ')}</dd></div>
          <div><dt>Runtime</dt><dd>{data.connectorStatus.runtime.replaceAll('_', ' ')}</dd></div>
        </dl>
      )}
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  )
}

const NODE_TYPES = { alidoraNode: AlidoraNode }

export default function DefinitionGraph({ map }) {
  const { nodes, edges } = useMemo(() => alidoraMapToFlow(map), [map])

  if (nodes.length === 0) {
    return <div className="canvas-empty">No system map is available for this workspace.</div>
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={NODE_TYPES}
      fitView
      nodesDraggable={false}
      nodesConnectable={false}
      nodesFocusable={false}
      elementsSelectable={false}
      edgesFocusable={false}
      deleteKeyCode={null}
      proOptions={{ hideAttribution: false }}
    >
      <Background />
      <Controls showInteractive={false} />
    </ReactFlow>
  )
}
