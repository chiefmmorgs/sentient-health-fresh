import React, { useCallback, useEffect, useMemo, useRef } from 'react'
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Connection,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  BackgroundVariant,
  NodeTypes,
  EdgeTypes,
  ReactFlowProvider,
  useReactFlow,
  ControlButton,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { Button } from '@/components/ui/button'

import { useTaskGraphStore } from '@/stores/taskGraphStore'
import TaskNodeComponent from './nodes/TaskNode'
import CustomEdge from './edges/CustomEdge'
import { convertToFlowNodes, convertToFlowEdges } from '@/lib/graphUtils'

const nodeTypes: NodeTypes = {
  taskNode: TaskNodeComponent,
}

const edgeTypes: EdgeTypes = {
  custom: CustomEdge,
}

const FlowContent: React.FC = () => {
  const { 
    nodes: graphNodes, 
    graphs, 
    selectedNodeId,
    selectedNodeIds,
    selectNode,
    toggleNodeSelection,
    showContextFlow,
    contextFlowMode,
    focusNodeId,
    getFilteredNodes,
    resetFilters
  } = useTaskGraphStore()

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const { fitView } = useReactFlow()

  const flowData = useMemo(() => {
    try {
      const filteredNodes = getFilteredNodes()
      
      const options = {
        selectedNodeId,
        filteredNodes,
        showContextFlow: showContextFlow || false,
        highlightMode: contextFlowMode || 'none',
        focusNodeId
      }
      
      const flowNodes = convertToFlowNodes(graphNodes, options).map(flowNode => ({
        ...flowNode,
        data: {
          ...flowNode.data,
          isMultiSelected: selectedNodeIds.has(flowNode.id)
        }
      }))
      
      const flowEdges = convertToFlowEdges(graphNodes, graphs || {}, options)
      
      return { nodes: flowNodes, edges: flowEdges }
    } catch (error) {
      console.error('Error converting graph data:', error)
      return { nodes: [], edges: [] }
    }
  }, [
    graphNodes,
    graphs,
    selectedNodeId, 
    selectedNodeIds, 
    showContextFlow, 
    contextFlowMode, 
    focusNodeId,
    getFilteredNodes
  ])

  // Track if this is the initial load
  const isInitialLoad = useRef(true)
  
  useEffect(() => {
    setNodes(flowData.nodes)
    setEdges(flowData.edges)
    
    // Only auto-fit on initial load or when nodes go from 0 to > 0
    if (flowData.nodes.length > 0 && isInitialLoad.current) {
      setTimeout(() => fitView({ padding: 0.2, duration: 800 }), 300)
      isInitialLoad.current = false
    }
  }, [flowData, setNodes, setEdges, fitView])

  const onNodeClick = useCallback(
    (event: React.MouseEvent, node: Node) => {
      const isMultiSelect = event.ctrlKey || event.metaKey
      toggleNodeSelection(node.id, isMultiSelect)
    },
    [toggleNodeSelection]
  )

  const onPaneClick = useCallback(() => {
    selectNode(undefined)
  }, [selectNode])

  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) => addEdge(params, eds))
    },
    [setEdges]
  )

  // Show filtered empty state
  if (Object.keys(graphNodes).length > 0) {
    const filteredNodes = getFilteredNodes()
    if (Object.keys(filteredNodes).length === 0) {
      return (
        <div className="w-full h-full flex items-center justify-center bg-muted/20">
          <div className="text-center max-w-md">
            <h3 className="text-lg font-medium mb-2">No Nodes Match Filters</h3>
            <p className="text-muted-foreground mb-4">
              {Object.keys(graphNodes).length} nodes available, but none match your current filters
            </p>
            <Button variant="outline" onClick={resetFilters}>
              Reset Filters
            </Button>
          </div>
        </div>
      )
    }
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      onNodeClick={onNodeClick}
      onPaneClick={onPaneClick}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      fitView={false}
      defaultViewport={{ x: 0, y: 0, zoom: 1 }}
      attributionPosition="bottom-left"
      proOptions={{ hideAttribution: true }}
      nodesDraggable={true}
      nodesConnectable={false}
      elementsSelectable={true}
      minZoom={0.1}
      maxZoom={4}
    >
      <Background 
        variant={BackgroundVariant.Dots} 
        gap={20} 
        size={1}
        className="opacity-30"
      />
      <Controls 
        className="bg-background border border-border rounded-lg shadow-lg" 
        showInteractive={false}
      >
        <ControlButton onClick={() => fitView({ padding: 0.2, duration: 800 })}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3 3h6v6H3V3zm12 0h6v6h-6V3zM3 15h6v6H3v-6zm12 0h6v6h-6v-6zm-4-4h2v2h-2v-2zm-4 0h2v2H7v-2zm8 0h2v2h-2v-2zm-4-4h2v2h-2V7z"/>
          </svg>
        </ControlButton>
      </Controls>
    </ReactFlow>
  )
}

const GraphVisualization: React.FC = () => {
  const { nodes: graphNodes, isLoading } = useTaskGraphStore()

  if (isLoading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-muted/20 to-muted/5">
        <div className="text-center animate-fade-in">
          <div className="relative mb-6">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-muted border-t-primary mx-auto shadow-lg"></div>
            <div className="absolute inset-0 rounded-full h-12 w-12 border-4 border-primary/20 mx-auto animate-pulse"></div>
          </div>
          <h3 className="text-lg font-medium mb-2 animate-slide-in">
            Setting up AI Agent System...
          </h3>
          <p className="text-muted-foreground animate-slide-in" style={{ animationDelay: '100ms' }}>
            Initializing task decomposition • Real-time updates will begin shortly
          </p>
        </div>
      </div>
    )
  }

  if (Object.keys(graphNodes).length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-muted/20">
        <div className="text-center">
          <h3 className="text-lg font-medium mb-2">Ready for New Project</h3>
          <p className="text-muted-foreground">
            Start a project to see the task decomposition graph
          </p>
          <div className="mt-4 text-xs text-muted-foreground">
            Real-time updates enabled ⚡
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full h-full bg-background">
      <ReactFlowProvider>
        <FlowContent />
      </ReactFlowProvider>
    </div>
  )
}

export default GraphVisualization 