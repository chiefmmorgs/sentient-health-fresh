import React, { useEffect, useState } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'

interface RestorationLog {
  timestamp: string
  event: string
  nodeId: string
  data: any
}

export const NodeRestorationDebugger: React.FC = () => {
  const [logs, setLogs] = useState<RestorationLog[]>([])
  const [isVisible, setIsVisible] = useState(false)
  
  const taskGraphStore = useTaskGraphStore()
  
  const addLog = (event: string, nodeId: string, data: any) => {
    const log: RestorationLog = {
      timestamp: new Date().toISOString(),
      event,
      nodeId,
      data: JSON.parse(JSON.stringify(data))
    }
    setLogs(prev => [log, ...prev.slice(0, 49)])
  }
  
  useEffect(() => {
    // Monitor node changes
    const unsubscribe = useTaskGraphStore.subscribe(
      (state) => state.nodes,
      (nodes, previousNodes) => {
        Object.entries(nodes).forEach(([nodeId, node]) => {
          const prevNode = previousNodes[nodeId]
          
          if (!prevNode) {
            // New node added
            addLog('NODE_ADDED', nodeId, {
              hasFullResult: node.full_result != null,
              hasAuxData: !!(node as any).aux_data,
              auxDataKeys: Object.keys((node as any).aux_data || {}),
              status: node.status
            })
          } else if (JSON.stringify(node) !== JSON.stringify(prevNode)) {
            // Node updated
            addLog('NODE_UPDATED', nodeId, {
              fullResultChanged: node.full_result !== prevNode.full_result,
              statusChanged: node.status !== prevNode.status,
              hasFullResult: node.full_result != null,
              hasAuxData: !!(node as any).aux_data,
              auxDataKeys: Object.keys((node as any).aux_data || {})
            })
          }
        })
      }
    )
    
    return unsubscribe
  }, [])
  
  if (!isVisible) {
    return (
      <button
        onClick={() => setIsVisible(true)}
        className="fixed bottom-16 right-4 bg-blue-500 text-white px-3 py-1 rounded text-xs z-50"
      >
        Node Debug
      </button>
    )
  }
  
  return (
    <div className="fixed bottom-16 right-4 w-96 h-96 bg-black text-green-400 text-xs overflow-auto p-2 rounded border z-50 font-mono">
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-white font-bold">Node Restoration Debugger</h3>
        <button
          onClick={() => setIsVisible(false)}
          className="text-red-400 hover:text-red-300"
        >
          ✕
        </button>
      </div>
      
      <div className="mb-2 text-yellow-400">
        <div>Total Nodes: {Object.keys(taskGraphStore.nodes).length}</div>
        <div>Nodes with full_result: {
          Object.values(taskGraphStore.nodes).filter(n => 
            n.full_result != null || (n as any).aux_data?.full_result != null
          ).length
        }</div>
      </div>
      
      <div className="space-y-1">
        {logs.map((log, index) => (
          <div key={index} className="border-b border-gray-700 pb-1">
            <div className="text-blue-400">{log.timestamp.split('T')[1].split('.')[0]}</div>
            <div className="text-yellow-400">{log.event} - {log.nodeId}</div>
            <div className="text-gray-300 pl-2">
              {JSON.stringify(log.data, null, 1).split('\n').slice(0, 2).join(' ')}
            </div>
          </div>
        ))}
      </div>
      
      <div className="mt-2 space-x-2">
        <button
          onClick={() => setLogs([])}
          className="bg-gray-700 px-2 py-1 rounded text-xs"
        >
          Clear
        </button>
        <button
          onClick={() => {
            const rootNode = Object.values(taskGraphStore.nodes).find(n => n.task_id === 'root')
            if (rootNode) {
              console.log('🐛 ROOT NODE DEBUG:', {
                hasFullResult: rootNode.full_result != null,
                hasAuxData: !!(rootNode as any).aux_data,
                auxDataKeys: Object.keys((rootNode as any).aux_data || {}),
                fullResultPreview: typeof rootNode.full_result === 'string' 
                  ? rootNode.full_result.substring(0, 100) 
                  : rootNode.full_result,
                auxFullResultPreview: typeof (rootNode as any).aux_data?.full_result === 'string'
                  ? (rootNode as any).aux_data.full_result.substring(0, 100)
                  : (rootNode as any).aux_data?.full_result
              })
            }
          }}
          className="bg-blue-700 px-2 py-1 rounded text-xs"
        >
          Debug Root
        </button>
      </div>
    </div>
  )
} 