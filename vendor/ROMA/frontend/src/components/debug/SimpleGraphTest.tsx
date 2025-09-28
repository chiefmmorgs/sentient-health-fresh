import React, { useEffect, useState } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'

const SimpleGraphTest: React.FC = () => {
  const [renderCount, setRenderCount] = useState(0)
  const nodes = useTaskGraphStore(state => state.nodes)
  const nodeCount = Object.keys(nodes).length

  useEffect(() => {
    setRenderCount(prev => prev + 1)
    console.log('🎨 SimpleGraphTest: Re-rendered!', { nodeCount, renderCount: renderCount + 1 })
  }, [nodes])

  return (
    <div className="w-full h-full flex flex-col items-center justify-center bg-muted/20">
      <div className="text-center max-w-md">
        <h2 className="text-xl font-bold mb-4">Simple Graph Test</h2>
        <div className="space-y-2 text-sm">
          <div><strong>Render Count:</strong> {renderCount}</div>
          <div><strong>Node Count:</strong> {nodeCount}</div>
          <div><strong>Time:</strong> {new Date().toLocaleTimeString()}</div>
        </div>
        
        {nodeCount > 0 && (
          <div className="mt-4 p-4 bg-background border rounded">
            <h3 className="font-medium mb-2">Nodes:</h3>
            <div className="space-y-1 text-xs font-mono">
              {Object.values(nodes).slice(0, 5).map((node) => (
                <div key={node.task_id} className="text-left">
                  {node.task_id}: {node.goal.slice(0, 30)}...
                </div>
              ))}
              {nodeCount > 5 && <div>... and {nodeCount - 5} more</div>}
            </div>
          </div>
        )}
        
        <div className="mt-4 text-xs text-muted-foreground">
          This component should update immediately when nodes change
        </div>
      </div>
    </div>
  )
}

export default SimpleGraphTest 