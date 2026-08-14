import { useMemo } from 'react'
import { ReactFlow, Background, Controls, Handle, Position } from '@xyflow/react'
import { definitionToFlow } from './graph.js'
import StepEdge from './StepEdge.jsx'

// Read-only rendering of one interface definition. Interaction — drag,
// connect, edit — is Step 9; here the graph only has to be truthful and
// readable: every agent visible, every step an edge in order, every
// approval interrupt unmistakable, dangling references shown as
// placeholders rather than hidden.

function StartNode() {
  return (
    <div className="node-start">
      Start
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

function AgentNode({ data }) {
  return (
    <div className={data.placeholder ? 'node-agent placeholder' : 'node-agent'}>
      <div className="node-name">{data.name}</div>
      <div className="node-role">{data.placeholder ? 'from an earlier save' : data.role}</div>
      {data.instructions && (
        <div className="node-instructions">{data.instructions}</div>
      )}
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

const NODE_TYPES = { cordiaStart: StartNode, cordiaAgent: AgentNode }
const EDGE_TYPES = { cordiaStep: StepEdge }

export default function DefinitionGraph({ definition }) {
  const { nodes, edges } = useMemo(() => definitionToFlow(definition), [definition])

  if (nodes.length === 0) {
    return (
      <div className="canvas-empty">
        This workspace is a blank canvas so far — its agents will appear
        here once it has some.
      </div>
    )
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={NODE_TYPES}
      edgeTypes={EDGE_TYPES}
      fitView
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      edgesFocusable={false}
      proOptions={{ hideAttribution: false }}
    >
      <Background />
      <Controls showInteractive={false} />
    </ReactFlow>
  )
}
