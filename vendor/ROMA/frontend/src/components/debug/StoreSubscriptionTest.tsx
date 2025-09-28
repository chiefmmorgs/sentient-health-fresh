import React, { useEffect, useState } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'

const StoreSubscriptionTest: React.FC = () => {
  const [renderCount, setRenderCount] = useState(0)
  const [lastUpdate, setLastUpdate] = useState<string>('')
  const nodes = useTaskGraphStore(state => state.nodes)
  const nodeCount = Object.keys(nodes).length

  // Force re-render counter
  useEffect(() => {
    setRenderCount(prev => prev + 1)
    setLastUpdate(new Date().toLocaleTimeString())
    console.log('🔄 StoreSubscriptionTest: Re-rendered due to store change')
    console.log('🔄 Current node count:', nodeCount)
    console.log('🔄 Node IDs:', Object.keys(nodes).slice(0, 5))
  }, [nodes, nodeCount])

  return (
    <div className="fixed top-4 left-4 z-50 bg-background/95 backdrop-blur border rounded-lg p-3 max-w-xs">
      <h3 className="font-medium text-sm mb-2">Store Subscription Test</h3>
      <div className="space-y-1 text-xs">
        <div>Render count: <span className="font-mono">{renderCount}</span></div>
        <div>Node count: <span className="font-mono">{nodeCount}</span></div>
        <div>Last update: <span className="font-mono">{lastUpdate}</span></div>
        <div className="text-xs text-muted-foreground">
          {Object.keys(nodes).slice(0, 3).join(', ')}
        </div>
      </div>
    </div>
  )
}

export default StoreSubscriptionTest 