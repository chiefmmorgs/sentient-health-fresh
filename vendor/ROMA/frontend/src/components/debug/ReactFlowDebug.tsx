import React, { useEffect, useState } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'

const ReactFlowDebug: React.FC = () => {
  const { nodes: graphNodes } = useTaskGraphStore()
  const [domNodes, setDomNodes] = useState<number>(0)
  const [reactFlowNodes, setReactFlowNodes] = useState<number>(0)

  useEffect(() => {
    const interval = setInterval(() => {
      // Check DOM for React Flow nodes
      const nodeElements = document.querySelectorAll('.react-flow__node')
      const nodeGroups = document.querySelectorAll('.react-flow__nodes > div')
      
      setDomNodes(nodeElements.length)
      setReactFlowNodes(nodeGroups.length)
      
      console.log('🔍 DOM DEBUG:', {
        storeNodes: Object.keys(graphNodes).length,
        domNodeElements: nodeElements.length,
        reactFlowNodeGroups: nodeGroups.length,
        nodeElementsIds: Array.from(nodeElements).map(el => el.getAttribute('data-id')),
        firstNodeVisible: nodeElements[0] ? window.getComputedStyle(nodeElements[0]).display : 'none'
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [graphNodes])

  return (
    <div className="fixed bottom-4 right-4 bg-white border border-gray-300 p-3 rounded shadow-lg text-xs z-50">
      <div><strong>React Flow Debug</strong></div>
      <div>Store Nodes: {Object.keys(graphNodes).length}</div>
      <div>DOM Node Elements: {domNodes}</div>
      <div>React Flow Groups: {reactFlowNodes}</div>
    </div>
  )
}

export default ReactFlowDebug 