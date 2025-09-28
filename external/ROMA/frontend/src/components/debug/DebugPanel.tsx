import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { webSocketService } from '@/services/websocketService'
import { Bug, Eye, EyeOff, RefreshCw, TestTube, Zap, Play } from 'lucide-react'

const DebugPanel: React.FC = () => {
  const [isVisible, setIsVisible] = useState(false)
  const [connectionInfo, setConnectionInfo] = useState<any>({})
  const [updateCount, setUpdateCount] = useState(0)
  const [lastNodeCount, setLastNodeCount] = useState(0)
  const { nodes, isConnected, isLoading, setData } = useTaskGraphStore()

  const currentNodeCount = Object.keys(nodes).length

  useEffect(() => {
    const interval = setInterval(() => {
      setConnectionInfo(webSocketService.getConnectionInfo())
    }, 1000)

    return () => clearInterval(interval)
  }, [])

  // Track node changes more precisely
  useEffect(() => {
    if (currentNodeCount !== lastNodeCount) {
      setUpdateCount(prev => prev + 1)
      setLastNodeCount(currentNodeCount)
      console.log('🔄 DebugPanel: Node count changed from', lastNodeCount, 'to', currentNodeCount)
    }
  }, [currentNodeCount, lastNodeCount])

  const forceRefresh = () => {
    console.log('🔄 Manual refresh triggered')
    window.location.reload()
  }

  const testStoreUpdate = () => {
    console.log('🧪 Testing direct store update...')
    const nodeId = 'test-store-' + Date.now()
    const testData = {
      all_nodes: {
        ...nodes,
        [nodeId]: {
          task_id: nodeId,
          goal: 'Test node created directly in store',
          task_type: 'TEST',
          node_type: 'EXECUTE' as const,
          layer: 0,
          status: 'DONE' as const,
        }
      },
      graphs: {},
      overall_project_goal: 'Test project'
    }
    
    console.log('🧪 Before store update - node count:', Object.keys(nodes).length)
    setData(testData)
    
    // Check after a brief delay
    setTimeout(() => {
      const newStore = useTaskGraphStore.getState()
      console.log('🧪 After store update - node count:', Object.keys(newStore.nodes).length)
    }, 100)
  }

  const testWebSocketSimulation = () => {
    console.log('🧪 Testing WebSocket simulation...')
    ;(webSocketService as any).simulateBackendUpdate()
  }

  const testManualNodeAdd = () => {
    console.log('🧪 Testing manual node addition to existing nodes...')
    const nodeId = 'manual-' + Date.now()
    
    // Get current store state
    const currentStore = useTaskGraphStore.getState()
    console.log('🧪 Current store nodes:', Object.keys(currentStore.nodes).length)
    
    // Create new nodes object with additional node
    const newNodes = {
      ...currentStore.nodes,
      [nodeId]: {
        task_id: nodeId,
        goal: 'Manually added test node',
        task_type: 'MANUAL_TEST',
        node_type: 'EXECUTE' as const,
        layer: 0,
        status: 'DONE' as const,
      }
    }
    
    // Update store with new nodes
    const testData = {
      all_nodes: newNodes,
      graphs: currentStore.graphs,
      overall_project_goal: currentStore.overallProjectGoal || 'Test project'
    }
    
    console.log('🧪 Updating store with', Object.keys(newNodes).length, 'nodes')
    setData(testData)
  }

  const testDirectStoreManipulation = () => {
    console.log('🧪 Testing DIRECT store manipulation...')
    
    // Get current store
    const store = useTaskGraphStore.getState()
    console.log('🧪 Current store nodes before:', Object.keys(store.nodes).length)
    
    // Create completely new node
    const nodeId = 'direct-' + Date.now()
    const newNode = {
      task_id: nodeId,
      goal: 'Direct store manipulation test',
      task_type: 'DIRECT_TEST',
      node_type: 'EXECUTE' as const,
      layer: 0,
      status: 'DONE' as const,
    }
    
    // Force a completely new nodes object
    const newNodes = { ...store.nodes, [nodeId]: newNode }
    
    console.log('🧪 New nodes object:', Object.keys(newNodes).length)
    console.log('🧪 New node added:', newNode)
    
    // Update store with new object
    useTaskGraphStore.setState({ 
      nodes: newNodes 
    })
    
    // Verify immediately
    const updatedStore = useTaskGraphStore.getState()
    console.log('🧪 Store after direct update:', Object.keys(updatedStore.nodes).length)
  }

  if (!isVisible) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setIsVisible(true)}
          className="bg-background/80 backdrop-blur"
        >
          <Bug className="w-4 h-4" />
          {currentNodeCount > 0 && (
            <Badge variant="secondary" className="ml-1 h-4 px-1 text-xs">
              {currentNodeCount}
            </Badge>
          )}
        </Button>
      </div>
    )
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 bg-background/95 backdrop-blur border rounded-lg p-4 max-w-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium text-sm">Debug Panel</h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsVisible(false)}
          className="h-6 w-6 p-0"
        >
          <EyeOff className="w-3 h-3" />
        </Button>
      </div>

      <div className="space-y-3">
        {/* Status */}
        <div className="space-y-2 text-xs">
          <div className="flex justify-between">
            <span>WebSocket:</span>
            <Badge variant={connectionInfo.connected ? "default" : "destructive"} className="text-xs">
              {connectionInfo.connected ? "Connected" : "Disconnected"}
            </Badge>
          </div>

          <div className="flex justify-between">
            <span>Loading:</span>
            <Badge variant={isLoading ? "secondary" : "outline"} className="text-xs">
              {isLoading ? "Yes" : "No"}
            </Badge>
          </div>

          <div className="flex justify-between">
            <span>Nodes:</span>
            <span className="font-mono">{currentNodeCount}</span>
          </div>

          <div className="flex justify-between">
            <span>WS Updates:</span>
            <span className="font-mono">{connectionInfo.updateCount || 0}</span>
          </div>

          <div className="flex justify-between">
            <span>UI Updates:</span>
            <span className="font-mono">{updateCount}</span>
          </div>

          <div className="flex justify-between">
            <span>Last Change:</span>
            <span className="font-mono text-xs">
              {lastNodeCount}→{currentNodeCount}
            </span>
          </div>
        </div>

        {/* Test Buttons */}
        <div className="space-y-2 pt-2 border-t">
          <Button
            variant="outline"
            size="sm"
            onClick={testStoreUpdate}
            className="w-full h-8 text-xs"
          >
            <TestTube className="w-3 h-3 mr-1" />
            Test Store Update
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            onClick={testManualNodeAdd}
            className="w-full h-8 text-xs"
          >
            <Play className="w-3 h-3 mr-1" />
            Add Manual Node
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            onClick={testWebSocketSimulation}
            className="w-full h-8 text-xs"
          >
            <Zap className="w-3 h-3 mr-1" />
            Test WebSocket
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            onClick={testDirectStoreManipulation}
            className="w-full h-8 text-xs"
          >
            <TestTube className="w-3 h-3 mr-1" />
            Direct Store Test
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            onClick={forceRefresh}
            className="w-full h-8 text-xs"
          >
            <RefreshCw className="w-3 h-3 mr-1" />
            Force Refresh
          </Button>
        </div>

        {/* Node Details */}
        <div className="text-xs text-muted-foreground pt-2 border-t">
          <div>Node IDs ({currentNodeCount}):</div>
          <div className="font-mono text-xs break-all max-h-20 overflow-y-auto">
            {Object.keys(nodes).slice(0, 5).map(id => (
              <div key={id}>{id.slice(0, 20)}...</div>
            ))}
            {Object.keys(nodes).length > 5 && <div>+{Object.keys(nodes).length - 5} more</div>}
          </div>
        </div>

        {connectionInfo.lastUpdate && (
          <div className="text-xs text-muted-foreground pt-2 border-t">
            Last WS: {new Date(connectionInfo.lastUpdate).toLocaleTimeString()}
          </div>
        )}
      </div>
    </div>
  )
}

export default DebugPanel 