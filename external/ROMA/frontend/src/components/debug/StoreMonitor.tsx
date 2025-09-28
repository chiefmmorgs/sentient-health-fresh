import React, { useEffect, useState } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'

const StoreMonitor: React.FC = () => {
  const [renderCount, setRenderCount] = useState(0)
  const [lastChange, setLastChange] = useState<string>('')
  
  // Subscribe to the ENTIRE store state
  const storeState = useTaskGraphStore()
  
  const nodeCount = Object.keys(storeState.nodes).length
  const nodeIds = Object.keys(storeState.nodes)

  useEffect(() => {
    setRenderCount(prev => prev + 1)
    setLastChange(new Date().toLocaleTimeString())
    console.log('🔥 StoreMonitor: STORE CHANGED!', {
      renderCount: renderCount + 1,
      nodeCount,
      nodeIds: nodeIds.slice(0, 3),
      timestamp: new Date().toISOString()
    })
  }, [storeState]) // React to ANY store changes

  return (
    <div className="fixed top-4 right-4 z-50 bg-red-100 dark:bg-red-900/30 border-2 border-red-500 rounded-lg p-3 max-w-xs">
      <h3 className="font-bold text-sm mb-2 text-red-800 dark:text-red-200">🔥 Store Monitor</h3>
      <div className="space-y-1 text-xs text-red-700 dark:text-red-300">
        <div><strong>Renders:</strong> <span className="font-mono">{renderCount}</span></div>
        <div><strong>Nodes:</strong> <span className="font-mono">{nodeCount}</span></div>
        <div><strong>Last:</strong> <span className="font-mono">{lastChange}</span></div>
        <div className="text-xs font-mono break-all">
          {nodeIds.slice(0, 2).join(', ')}
        </div>
        <div className="pt-1 border-t text-xs">
          Loading: {storeState.isLoading ? 'YES' : 'NO'}
        </div>
      </div>
    </div>
  )
}

export default StoreMonitor 