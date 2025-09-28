import React, { useMemo } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  ChevronRight,
  Home,
  ArrowUp,
  ArrowDown,
  Layers,
  GitBranch,
  Navigation
} from 'lucide-react'
import { cn, getStatusColor } from '@/lib/utils'
import type { TaskNode } from '@/types'

interface NavigationPath {
  nodeId: string
  goal: string
  layer: number
  status: string
}

const NodeNavigator: React.FC = () => {
  const { selectedNodeId, nodes, selectNode } = useTaskGraphStore()
  
  const selectedNode = selectedNodeId ? nodes[selectedNodeId] : null

  // Build navigation path from root to current node
  const navigationPath = useMemo(() => {
    if (!selectedNode) return []

    const path: NavigationPath[] = []
    let currentNode = selectedNode

    // Build path from current node to root
    while (currentNode) {
      path.unshift({
        nodeId: currentNode.task_id,
        goal: currentNode.goal,
        layer: currentNode.layer,
        status: currentNode.status
      })

      // Move to parent
      if (currentNode.parent_node_id) {
        currentNode = nodes[currentNode.parent_node_id]
      } else {
        break
      }
    }

    return path
  }, [selectedNode, nodes])

  // Get sibling nodes (nodes with same parent and layer)
  const siblings = useMemo(() => {
    if (!selectedNode || !selectedNode.parent_node_id) return []

    return Object.values(nodes).filter(node => 
      node.parent_node_id === selectedNode.parent_node_id &&
      node.task_id !== selectedNode.task_id
    ).sort((a, b) => a.goal.localeCompare(b.goal))
  }, [selectedNode, nodes])

  // Get child nodes
  const children = useMemo(() => {
    if (!selectedNode?.planned_sub_task_ids) return []

    return selectedNode.planned_sub_task_ids
      .map(id => nodes[id])
      .filter(Boolean)
      .sort((a, b) => a.goal.localeCompare(b.goal))
  }, [selectedNode, nodes])

  // Get nodes at the same layer across the entire graph
  const layerPeers = useMemo(() => {
    if (!selectedNode) return []

    return Object.values(nodes)
      .filter(node => 
        node.layer === selectedNode.layer && 
        node.task_id !== selectedNode.task_id
      )
      .sort((a, b) => a.goal.localeCompare(b.goal))
      .slice(0, 5) // Limit to 5 for UI space
  }, [selectedNode, nodes])

  const navigateToRoot = () => {
    const rootNode = Object.values(nodes).find(node => node.layer === 0)
    if (rootNode) {
      console.log('Navigating to root:', rootNode.task_id)
      selectNode(rootNode.task_id)
    }
  }

  const truncateGoal = (goal: string, maxLength: number = 30) => {
    return goal.length > maxLength ? goal.substring(0, maxLength) + '...' : goal
  }

  const handleNavigation = (nodeId: string, context: string) => {
    console.log(`Navigating via ${context}:`, nodeId)
    selectNode(nodeId)
  }

  if (!selectedNode) return null

  return (
    <div className="space-y-4">
      {/* Breadcrumb Navigation */}
      <div>
        <div className="flex items-center space-x-2 mb-2">
          <Navigation className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium">Navigation Path</span>
        </div>
        
        <div className="space-y-1">
          {navigationPath.map((pathNode, index) => (
            <div key={pathNode.nodeId} className="flex items-center space-x-2">
              <div className="flex items-center space-x-1 text-xs text-muted-foreground min-w-0 flex-shrink-0">
                <Layers className="w-3 h-3" />
                <span>L{pathNode.layer}</span>
              </div>
              
              <Button
                variant={pathNode.nodeId === selectedNodeId ? "default" : "ghost"}
                size="sm"
                onClick={() => handleNavigation(pathNode.nodeId, 'breadcrumb')}
                className={cn(
                  "h-7 px-2 justify-start text-xs flex-1 min-w-0",
                  pathNode.nodeId === selectedNodeId && "bg-primary/10"
                )}
              >
                <div className={cn("w-2 h-2 rounded-full mr-2 flex-shrink-0", getStatusColor(pathNode.status))} />
                <span className="truncate">{truncateGoal(pathNode.goal)}</span>
              </Button>
              
              {index < navigationPath.length - 1 && (
                <ChevronRight className="w-3 h-3 text-muted-foreground flex-shrink-0" />
              )}
            </div>
          ))}
        </div>

        {navigationPath.length > 1 && (
          <Button
            variant="outline"
            size="sm"
            onClick={navigateToRoot}
            className="mt-2 h-7 px-2 text-xs"
          >
            <Home className="w-3 h-3 mr-1" />
            Go to Root
          </Button>
        )}
      </div>

      {/* Parent/Child Quick Navigation */}
      {(selectedNode.parent_node_id || children.length > 0) && (
        <div>
          <div className="flex items-center space-x-2 mb-2">
            <ArrowUp className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-medium">Quick Navigation</span>
          </div>
          
          <div className="space-y-1">
            {selectedNode.parent_node_id && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleNavigation(selectedNode.parent_node_id!, 'parent')}
                className="h-7 px-2 text-xs w-full justify-start"
              >
                <ArrowUp className="w-3 h-3 mr-1" />
                Go to Parent
              </Button>
            )}
            
            {children.length > 0 && (
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground px-2">
                  Children ({children.length}):
                </div>
                <div className="max-h-20 overflow-y-auto space-y-1">
                  {children.slice(0, 3).map((child) => (
                    <Button
                      key={child.task_id}
                      variant="ghost"
                      size="sm"
                      onClick={() => handleNavigation(child.task_id, 'child')}
                      className="h-6 px-2 text-xs w-full justify-start"
                    >
                      <ArrowDown className="w-3 h-3 mr-1" />
                      <div className={cn("w-2 h-2 rounded-full mr-1", getStatusColor(child.status))} />
                      <span className="truncate">{truncateGoal(child.goal, 25)}</span>
                    </Button>
                  ))}
                  {children.length > 3 && (
                    <div className="text-xs text-muted-foreground px-2">
                      +{children.length - 3} more...
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Sibling Navigation */}
      {siblings.length > 0 && (
        <div>
          <div className="flex items-center space-x-2 mb-2">
            <GitBranch className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-medium">Sibling Tasks ({siblings.length})</span>
          </div>
          
          <div className="space-y-1 max-h-24 overflow-y-auto">
            {siblings.slice(0, 4).map((sibling) => (
              <Button
                key={sibling.task_id}
                variant="ghost"
                size="sm"
                onClick={() => handleNavigation(sibling.task_id, 'sibling')}
                className="h-6 px-2 text-xs w-full justify-start"
              >
                <div className={cn("w-2 h-2 rounded-full mr-2", getStatusColor(sibling.status))} />
                <span className="truncate">{truncateGoal(sibling.goal, 28)}</span>
              </Button>
            ))}
            {siblings.length > 4 && (
              <div className="text-xs text-muted-foreground px-2">
                +{siblings.length - 4} more siblings...
              </div>
            )}
          </div>
        </div>
      )}

      {/* Layer Peers */}
      {layerPeers.length > 0 && (
        <div>
          <div className="flex items-center space-x-2 mb-2">
            <Layers className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-medium">
              Layer {selectedNode.layer} ({layerPeers.length}+ tasks)
            </span>
          </div>
          
          <div className="space-y-1 max-h-20 overflow-y-auto">
            {layerPeers.map((peer) => (
              <Button
                key={peer.task_id}
                variant="ghost"
                size="sm"
                onClick={() => handleNavigation(peer.task_id, 'layer-peer')}
                className="h-6 px-2 text-xs w-full justify-start"
              >
                <div className={cn("w-2 h-2 rounded-full mr-2", getStatusColor(peer.status))} />
                <span className="truncate">{truncateGoal(peer.goal, 28)}</span>
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Quick Stats */}
      <div className="border-t border-border/50 pt-3">
        <div className="text-xs text-muted-foreground mb-2">Quick Stats</div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Current Layer</span>
            <Badge variant="outline" className="text-xs">
              L{selectedNode.layer}
            </Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Total Nodes</span>
            <Badge variant="outline" className="text-xs">
              {Object.keys(nodes).length}
            </Badge>
          </div>
        </div>
        
        {navigationPath.length > 1 && (
          <div className="mt-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Depth from Root</span>
              <Badge variant="outline" className="text-xs">
                {navigationPath.length - 1} levels
              </Badge>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default NodeNavigator 