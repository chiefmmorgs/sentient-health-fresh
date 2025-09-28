import { Node, Edge } from 'reactflow'
import type { TaskNode } from '@/types'

interface ConversionOptions {
  selectedNodeId?: string
  filteredNodes?: Record<string, TaskNode>
  showContextFlow?: boolean
  highlightMode?: string
  focusNodeId?: string
}

export function convertToFlowNodes(
  graphNodes: Record<string, TaskNode>, 
  options: ConversionOptions = {}
): Node[] {
  const { filteredNodes = graphNodes } = options
  
  // Convert the filtered nodes object to an array
  const tasks = Object.values(filteredNodes)
  
  // Group nodes by layer for proper hierarchical layout
  const nodesByLayer: Record<number, TaskNode[]> = {}
  tasks.forEach(task => {
    const layer = task.layer || 0
    if (!nodesByLayer[layer]) {
      nodesByLayer[layer] = []
    }
    nodesByLayer[layer].push(task)
  })
  
  return tasks.map((task) => {
    const layer = task.layer || 0
    const nodesInLayer = nodesByLayer[layer] || []
    const indexInLayer = nodesInLayer.findIndex(n => n.task_id === task.task_id)
    const totalInLayer = nodesInLayer.length
    
    // Calculate position based on layer and position within layer
    const layerHeight = 150
    const nodeSpacing = 280
    const y = layer * layerHeight
    
    // Center nodes horizontally within their layer
    const totalWidth = Math.max(0, (totalInLayer - 1) * nodeSpacing)
    const startX = -totalWidth / 2
    const x = startX + (indexInLayer * nodeSpacing)
    
    return {
      id: task.task_id,
      type: 'taskNode',
      position: { x, y },
      data: {
        node: task,
        label: task.goal || task.task_id,
        status: task.status,
        type: task.task_type,
        isHighlighted: options.selectedNodeId === task.task_id,
        isDimmed: false,
        isMultiSelected: false,
        highlightMode: options.highlightMode || 'none'
      }
    }
  })
}

export function convertToFlowEdges(
  graphNodes: Record<string, TaskNode>, 
  graphs: Record<string, any> = {}, 
  options: ConversionOptions = {}
): Edge[] {
  const { filteredNodes = graphNodes } = options
  const edges: Edge[] = []
  
  // Convert the filtered nodes object to an array
  const tasks = Object.values(filteredNodes)
  
  tasks.forEach(task => {
    if (task.parent_node_id && filteredNodes[task.parent_node_id]) {
      edges.push({
        id: `${task.parent_node_id}-${task.task_id}`,
        source: task.parent_node_id,
        target: task.task_id,
        type: 'smoothstep',
        animated: task.status === 'RUNNING' || task.status === 'EXECUTING'
      })
    }
  })
  
  return edges
}

export function layoutNodes(nodes: Node[], edges: Edge[]): Node[] {
  // Simple hierarchical layout
  const nodeMap = new Map(nodes.map(node => [node.id, node]))
  const positioned = new Set<string>()
  const levels: string[][] = []
  
  // Find root nodes (no incoming edges)
  const hasIncoming = new Set(edges.map(edge => edge.target))
  const rootNodes = nodes.filter(node => !hasIncoming.has(node.id))
  
  // BFS to assign levels
  const queue = rootNodes.map(node => ({ id: node.id, level: 0 }))
  
  while (queue.length > 0) {
    const { id, level } = queue.shift()!
    
    if (positioned.has(id)) continue
    positioned.add(id)
    
    if (!levels[level]) levels[level] = []
    levels[level].push(id)
    
    // Add children to next level
    const children = edges
      .filter(edge => edge.source === id)
      .map(edge => edge.target)
    
    children.forEach(childId => {
      if (!positioned.has(childId)) {
        queue.push({ id: childId, level: level + 1 })
      }
    })
  }
  
  // Position nodes
  const levelHeight = 150
  const nodeWidth = 280
  
  return nodes.map(node => {
    const level = levels.findIndex(levelNodes => levelNodes.includes(node.id))
    const indexInLevel = levels[level]?.indexOf(node.id) || 0
    const nodesInLevel = levels[level]?.length || 1
    
    const totalWidth = Math.max(0, (nodesInLevel - 1) * nodeWidth)
    const startX = -totalWidth / 2
    const x = startX + (indexInLevel * nodeWidth)
    const y = level * levelHeight
    
    return {
      ...node,
      position: { x, y }
    }
  })
} 