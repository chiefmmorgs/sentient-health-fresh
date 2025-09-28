import React, { useState } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { useProjectStore } from '@/stores/projectStore'

const ProjectDebugPanel: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false)
  const { nodes, currentProjectId, projectData } = useTaskGraphStore()
  const { currentProjectId: projectStoreCurrentId } = useProjectStore()

  const handleForceSave = () => {
    const websocketService = (window as any).websocketService
    if (websocketService && websocketService.forceSaveCurrentProject) {
      websocketService.forceSaveCurrentProject()
      console.log('🚨 DEBUG - Force save triggered')
    } else {
      console.error('❌ WebSocket service not available')
    }
  }

  const handleForceRestore = () => {
    const websocketService = (window as any).websocketService
    if (websocketService && websocketService.forceRestoreCurrentProject) {
      websocketService.forceRestoreCurrentProject()
      console.log('🚨 DEBUG - Force restore triggered')
    } else {
      console.error('❌ WebSocket service not available')
    }
  }

  const handleRerunProject = () => {
    if (currentProjectId) {
      const confirmed = confirm('This will re-run the project execution from scratch. All current progress will be lost. Are you sure?')
      if (confirmed) {
        const websocketService = (window as any).websocketService
        if (websocketService && websocketService.rerunProject) {
          websocketService.rerunProject(currentProjectId)
          console.log('🚨 DEBUG - Project re-run triggered for:', currentProjectId)
        } else {
          console.error('❌ WebSocket service not available')
        }
      }
    } else {
      console.error('❌ No current project to re-run')
    }
  }

  const rootNode = Object.values(nodes).find(node => node.layer === 0 && !node.parent_node_id)
  const hasNodes = Object.keys(nodes).length > 0

  if (!isOpen) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <button
          onClick={() => setIsOpen(true)}
          className={`px-3 py-2 rounded text-sm font-mono shadow-lg ${
            hasNodes ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'
          } text-white`}
        >
          🚨 DEBUG {hasNodes ? '✅' : '❌'}
        </button>
      </div>
    )
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 bg-black text-green-400 p-4 rounded-lg font-mono text-xs max-w-md max-h-96 overflow-auto shadow-2xl border border-green-500">
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-sm font-bold text-red-400">🚨 PROJECT DEBUG PANEL</h3>
        <button onClick={() => setIsOpen(false)} className="text-red-400 hover:text-red-300">✕</button>
      </div>
      
      <div className="space-y-2">
        <div className="border-b border-gray-700 pb-2">
          <strong className="text-yellow-400">Current Project IDs:</strong>
          <div>TaskGraph: <span className="text-white">{currentProjectId || 'none'}</span></div>
          <div>ProjectStore: <span className="text-white">{projectStoreCurrentId || 'none'}</span></div>
          <div>Match: {currentProjectId === projectStoreCurrentId ? '✅' : '❌'}</div>
        </div>
        
        <div className="border-b border-gray-700 pb-2">
          <strong className="text-yellow-400">Current Display:</strong>
          <div>Nodes: <span className={`text-white ${hasNodes ? 'text-green-400' : 'text-red-400'}`}>{Object.keys(nodes).length}</span></div>
          <div>Root Node: {rootNode ? '✅' : '❌'}</div>
          {rootNode && (
            <div className="ml-2">
              <div>Status: <span className="text-white">{rootNode.status}</span></div>
              <div>Has Full Result: {rootNode.full_result ? '✅' : '❌'}</div>
              <div>Has Aux Full Result: {(rootNode as any).aux_data?.full_result ? '✅' : '❌'}</div>
              {rootNode.full_result && (
                <div>Preview: <span className="text-blue-400">{rootNode.full_result.substring(0, 50)}...</span></div>
              )}
            </div>
          )}
        </div>
        
        <div className="border-b border-gray-700 pb-2">
          <strong className="text-yellow-400">Project Data Cache:</strong>
          <div>Cached Projects: <span className="text-white">{Object.keys(projectData).length}</span></div>
          {currentProjectId && projectData[currentProjectId] && (
            <div>Current Cached Nodes: <span className="text-white">{Object.keys(projectData[currentProjectId].nodes).length}</span></div>
          )}
        </div>
        
        <div className="space-y-1">
          <button
            onClick={handleForceRestore}
            className="bg-green-600 text-white px-2 py-1 rounded text-xs w-full hover:bg-green-700"
          >
            🔄 Force Restore Project
          </button>
          <button
            onClick={handleForceSave}
            className="bg-blue-600 text-white px-2 py-1 rounded text-xs w-full hover:bg-blue-700"
          >
            💾 Force Save Project
          </button>
          <button
            onClick={handleRerunProject}
            className="bg-red-600 text-white px-2 py-1 rounded text-xs w-full hover:bg-red-700"
            disabled={!currentProjectId}
          >
            🚨 Re-run Project Execution
          </button>
        </div>
        
        <div className="text-xs text-gray-400 mt-2">
          <div>💡 <strong>If nodes are missing:</strong></div>
          <div>1. Try "Force Restore" first</div>
          <div>2. If still empty, use "Re-run Project"</div>
          <div>3. Check console for detailed logs</div>
          <div className="mt-1 text-yellow-400">
            <strong>Status:</strong> {hasNodes ? 'Data Found ✅' : 'No Data ❌'}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ProjectDebugPanel 