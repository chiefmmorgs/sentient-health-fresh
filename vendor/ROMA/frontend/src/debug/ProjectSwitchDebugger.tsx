import React, { useEffect, useState } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { useProjectStore } from '@/stores/projectStore'

interface DebugLog {
  timestamp: string
  event: string
  data: any
}

export const ProjectSwitchDebugger: React.FC = () => {
  const [logs, setLogs] = useState<DebugLog[]>([])
  const [isVisible, setIsVisible] = useState(false)
  
  const taskGraphStore = useTaskGraphStore()
  const projectStore = useProjectStore()
  
  const addLog = (event: string, data: any) => {
    const log: DebugLog = {
      timestamp: new Date().toISOString(),
      event,
      data: JSON.parse(JSON.stringify(data)) // Deep clone to prevent reference issues
    }
    setLogs(prev => [log, ...prev.slice(0, 49)]) // Keep last 50 logs
  }
  
  useEffect(() => {
    // Monitor store changes
    const unsubscribeTaskGraph = useTaskGraphStore.subscribe(
      (state) => state.currentProjectId,
      (currentProjectId, previousProjectId) => {
        if (currentProjectId !== previousProjectId) {
          addLog('TASK_GRAPH_PROJECT_CHANGE', {
            from: previousProjectId,
            to: currentProjectId,
            nodeCount: Object.keys(useTaskGraphStore.getState().nodes).length
          })
        }
      }
    )
    
    const unsubscribeProject = useProjectStore.subscribe(
      (state) => state.currentProjectId,
      (currentProjectId, previousProjectId) => {
        if (currentProjectId !== previousProjectId) {
          addLog('PROJECT_STORE_PROJECT_CHANGE', {
            from: previousProjectId,
            to: currentProjectId
          })
        }
      }
    )
    
    // Monitor WebSocket events
    const originalEmit = (window as any).webSocketService?.socket?.emit
    if (originalEmit) {
      (window as any).webSocketService.socket.emit = function(event: string, ...args: any[]) {
        if (event.includes('project') || event.includes('switch')) {
          addLog('WEBSOCKET_EMIT', { event, args })
        }
        return originalEmit.apply(this, [event, ...args])
      }
    }
    
    return () => {
      unsubscribeTaskGraph()
      unsubscribeProject()
    }
  }, [])
  
  if (!isVisible) {
    return (
      <button
        onClick={() => setIsVisible(true)}
        className="fixed bottom-4 right-4 bg-red-500 text-white px-3 py-1 rounded text-xs z-50"
      >
        Debug
      </button>
    )
  }
  
  return (
    <div className="fixed bottom-4 right-4 w-96 h-96 bg-black text-green-400 text-xs overflow-auto p-2 rounded border z-50 font-mono">
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-white font-bold">Project Switch Debugger</h3>
        <button
          onClick={() => setIsVisible(false)}
          className="text-red-400 hover:text-red-300"
        >
          ✕
        </button>
      </div>
      
      <div className="mb-2 text-yellow-400">
        <div>TaskGraph Project: {taskGraphStore.currentProjectId || 'none'}</div>
        <div>Project Store: {projectStore.currentProjectId || 'none'}</div>
        <div>Nodes: {Object.keys(taskGraphStore.nodes).length}</div>
        <div>Project Data: {Object.keys(taskGraphStore.projectData).length}</div>
      </div>
      
      <div className="space-y-1">
        {logs.map((log, index) => (
          <div key={index} className="border-b border-gray-700 pb-1">
            <div className="text-blue-400">{log.timestamp.split('T')[1].split('.')[0]}</div>
            <div className="text-yellow-400">{log.event}</div>
            <div className="text-gray-300 pl-2">
              {JSON.stringify(log.data, null, 1).split('\n').slice(0, 3).join(' ')}
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
            const data = {
              stores: {
                taskGraph: {
                  currentProjectId: taskGraphStore.currentProjectId,
                  nodeCount: Object.keys(taskGraphStore.nodes).length,
                  projectDataKeys: Object.keys(taskGraphStore.projectData)
                },
                project: {
                  currentProjectId: projectStore.currentProjectId,
                  projectCount: projectStore.projects.length
                }
              },
              logs: logs.slice(0, 10)
            }
            console.log('🐛 DEBUG DUMP:', data)
            addLog('DEBUG_DUMP', data)
          }}
          className="bg-blue-700 px-2 py-1 rounded text-xs"
        >
          Dump
        </button>
      </div>
    </div>
  )
} 