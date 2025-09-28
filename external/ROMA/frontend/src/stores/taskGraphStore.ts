import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'
import type { TaskNode, APIResponse, HITLRequest, HITLResponse } from '@/types'

// Filtering interfaces
interface GraphFilters {
  statuses: string[]
  taskTypes: string[]
  nodeTypes: ('PLAN' | 'EXECUTE')[]
  layers: number[]
  agentNames: string[]
  searchTerm: string
  showOnlySelected: boolean
}

interface HITLLog {
  checkpoint_name: string
  context_message: string
  node_id: string
  current_attempt: number
  timestamp: string
  request_id: string
}

// NEW: Project-specific data structure
interface ProjectData {
  nodes: Record<string, TaskNode>
  graphs: Record<string, any>
  overallProjectGoal?: string
  lastUpdated: number
}

interface TaskGraphState {
  // Current display data (what's shown in UI)
  nodes: Record<string, TaskNode>
  graphs: Record<string, any>
  overallProjectGoal?: string
  
  // NEW: Project-specific data storage
  currentProjectId?: string
  projectData: Record<string, ProjectData>
  
  // UI State
  isConnected: boolean
  isLoading: boolean
  selectedNodeId?: string
  showContextFlow: boolean
  
  // Filtering State
  filters: GraphFilters
  isFilterPanelOpen: boolean
  
  // Context Flow State
  contextFlowMode: 'none' | 'dataFlow' | 'executionPath' | 'subtree'
  focusNodeId?: string
  
  // Multi-Selection State
  selectedNodeIds: Set<string>
  isMultiSelectMode: boolean
  comparisonView: 'cards' | 'table' | 'timeline' | 'metrics'
  isComparisonPanelOpen: boolean
  
  // Tool Calls Modal State
  isToolCallsModalOpen: boolean
  
  // HITL State
  currentHITLRequest: HITLRequest | undefined
  isHITLModalOpen: boolean
  
  // HITL Logs
  hitlLogs: HITLLog[]
  
  // Actions
  setData: (data: APIResponse) => void
  setConnectionStatus: (status: boolean) => void
  setLoading: (loading: boolean) => void
  selectNode: (nodeId?: string) => void
  toggleContextFlow: () => void
  
  // NEW: Project-specific actions
  setCurrentProject: (projectId: string) => void
  setProjectData: (projectId: string, data: APIResponse) => void
  getProjectData: (projectId: string) => ProjectData | null
  clearProjectData: (projectId: string) => void
  switchToProject: (projectId: string) => void
  
  // Filter Actions
  updateFilters: (filters: Partial<GraphFilters>) => void
  resetFilters: () => void
  toggleFilterPanel: () => void
  setSearchTerm: (term: string) => void
  showActiveNodes: () => void
  showProblematicNodes: () => void
  showCompletedNodes: () => void
  showCurrentLayer: () => void
  
  // Context Flow Actions
  setContextFlowMode: (mode: 'none' | 'dataFlow' | 'executionPath' | 'subtree') => void
  setFocusNode: (nodeId?: string) => void
  zoomToSubtree: (nodeId: string) => void
  
  // Multi-Selection Actions
  toggleNodeSelection: (nodeId: string, isMultiSelect?: boolean) => void
  selectAllNodes: () => void
  selectFilteredNodes: () => void
  clearSelection: () => void
  invertSelection: () => void
  setMultiSelectMode: (enabled: boolean) => void
  setComparisonView: (view: 'cards' | 'table' | 'timeline' | 'metrics') => void
  
  // Tool Calls Modal actions
  openToolCallsModal: () => void
  closeToolCallsModal: () => void
  toggleComparisonPanel: () => void
  
  // Computed Properties
  getFilteredNodes: () => Record<string, TaskNode>
  getAvailableFilters: () => {
    statuses: string[]
    taskTypes: string[]
    nodeTypes: ('PLAN' | 'EXECUTE')[]
    layers: number[]
    agentNames: string[]
  }
  getSelectedNodes: () => TaskNode[]
  getSelectionStats: () => {
    total: number
    byStatus: Record<string, number>
    byTaskType: Record<string, number>
    byLayer: Record<number, number>
    avgExecutionTime: number
    successRate: number
  }
  
  // HITL Actions
  setHITLRequest: (request: HITLRequest | null) => void
  clearHITLRequest: () => void
  respondToHITL: (response: HITLResponse) => void
  closeHITLModal: () => void
  
  // HITL Logs Actions
  addHITLLog: (log: HITLLog) => void
  clearHITLLogs: () => void
  
  // New properties
  hitlRequest: HITLRequest | null
}

const defaultFilters: GraphFilters = {
  statuses: [],
  taskTypes: [],
  nodeTypes: [],
  layers: [],
  agentNames: [],
  searchTerm: '',
  showOnlySelected: false
}

export const useTaskGraphStore = create<TaskGraphState>()(
  subscribeWithSelector((set, get) => ({
    // Initial state
    nodes: {},
    graphs: {},
    overallProjectGoal: undefined,
    
    // NEW: Project-specific state
    currentProjectId: undefined,
    projectData: {},
    
    isConnected: false,
    isLoading: false,
    selectedNodeId: undefined,
    showContextFlow: true,
    
    // Filtering state
    filters: defaultFilters,
    isFilterPanelOpen: false,
    
    // Context Flow state
    contextFlowMode: 'none',
    focusNodeId: undefined,
    
    // Multi-Selection state
    selectedNodeIds: new Set<string>(),
    isMultiSelectMode: false,
    comparisonView: 'cards',
    isComparisonPanelOpen: false,
    
    // Tool Calls Modal state
    isToolCallsModalOpen: false,
    
    currentHITLRequest: undefined,
    isHITLModalOpen: false,
    
    // HITL Logs
    hitlLogs: [],
    
    // Actions
    setData: (data: APIResponse) => {
      console.log('🏪 STORE: setData called with:', data)
      
      const prevState = get()
      const prevNodes = prevState.nodes
      const prevNodeCount = Object.keys(prevNodes).length
      const prevNodeIds = Object.keys(prevNodes).sort()
      
      const newNodes = data.all_nodes || {}
      const newNodeCount = Object.keys(newNodes).length
      const newNodeIds = Object.keys(newNodes).sort()
      
      // ENHANCED LOGGING: Log each node's goal
      console.log('🏪 STORE: Node goals comparison:')
      newNodeIds.forEach(id => {
        const prevGoal = prevNodes[id]?.goal
        const newGoal = newNodes[id]?.goal
        if (prevGoal !== newGoal) {
          console.log(`  📝 Node ${id} goal changed:`)
          console.log(`     OLD: "${prevGoal}"`)
          console.log(`     NEW: "${newGoal}"`)
        } else if (newGoal) {
          console.log(`  ✓ Node ${id} goal unchanged: "${newGoal?.substring(0, 50)}..."`)
        }
      })
      
      // Check for duplicate goals
      const goalCounts = new Map<string, string[]>()
      Object.entries(newNodes).forEach(([id, node]) => {
        const goal = node.goal
        if (!goalCounts.has(goal)) {
          goalCounts.set(goal, [])
        }
        goalCounts.get(goal)!.push(id)
      })
      
      console.log('🏪 STORE: Goal duplication check:')
      goalCounts.forEach((nodeIds, goal) => {
        if (nodeIds.length > 1) {
          console.warn(`  ⚠️ DUPLICATE GOAL DETECTED: ${nodeIds.length} nodes have the same goal:`)
          console.warn(`     Goal: "${goal?.substring(0, 100)}..."`)
          console.warn(`     Nodes: ${nodeIds.join(', ')}`)
        }
      })
      
      const actuallyDifferent = JSON.stringify(prevNodeIds) !== JSON.stringify(newNodeIds)
      
      console.log('🏪 STORE: Detailed comparison:')
      console.log('  Previous nodes:', prevNodeCount, prevNodeIds.slice(0, 3))
      console.log('  New nodes:', newNodeCount, newNodeIds.slice(0, 3))
      console.log('  Actually different:', actuallyDifferent)
      console.log('  Node count changed:', prevNodeCount !== newNodeCount)
      
      // Always preserve HITL request if one exists
      const currentHITLRequest = prevState.hitlRequest
      
      if (currentHITLRequest) {
        console.log('🔒 STORE: Preserving active HITL request during update')
      }
      
      // Force update by creating completely new objects
      const newState = {
        nodes: { ...newNodes }, // Shallow copy to ensure new reference
        graphs: { ...(data.graphs || {}) },
        overallProjectGoal: data.overall_project_goal,
        isLoading: newNodeCount === 0 ? prevState.isLoading : false,
        // Always preserve HITL state if it exists
        hitlRequest: currentHITLRequest,
        currentHITLRequest: currentHITLRequest,
        isHITLModalOpen: !!currentHITLRequest,
      }
      
      console.log('🏪 STORE: Setting new state:', {
        nodeCount: Object.keys(newState.nodes).length,
        nodeIds: Object.keys(newState.nodes).slice(0, 3),
        isLoading: newState.isLoading,
        hitlPreserved: !!newState.hitlRequest
      })
      
      // Update store
      set(newState)
      
      // Verify update worked
      const verifyState = get()
      const verifyNodeCount = Object.keys(verifyState.nodes).length
      
      console.log('🏪 STORE: Update verification:')
      console.log('  Expected node count:', newNodeCount)
      console.log('  Actual node count:', verifyNodeCount)
      console.log('  Update successful:', verifyNodeCount === newNodeCount)
      
      if (verifyNodeCount !== newNodeCount) {
        console.error('🚨 STORE: Update failed! Expected', newNodeCount, 'got', verifyNodeCount)
      } else {
        console.log('✅ STORE: Update successful!')
      }
    },
    
    // NEW: Project-specific actions
    setCurrentProject: (projectId: string) => {
      console.log('🏪 STORE: Setting current project:', projectId)
      set({ currentProjectId: projectId })
    },
    
    setProjectData: (projectId: string, data: APIResponse) => {
      console.log('🏪 STORE: Setting project data for:', projectId, 'nodes:', Object.keys(data.all_nodes || {}).length)
      
      const projectData: ProjectData = {
        nodes: data.all_nodes || {},
        graphs: data.graphs || {},
        overallProjectGoal: data.overall_project_goal,
        lastUpdated: Date.now()
      }
      
      set(state => ({
        projectData: {
          ...state.projectData,
          [projectId]: projectData
        }
      }))
      
      // If this is the current project, also update display
      const currentProjectId = get().currentProjectId
      if (projectId === currentProjectId) {
        console.log('🏪 STORE: Updating display for current project:', projectId)
        get().setData(data)
      }
    },
    
    getProjectData: (projectId: string): ProjectData | null => {
      const { projectData } = get()
      return projectData[projectId] || null
    },
    
    clearProjectData: (projectId: string) => {
      console.log('🏪 STORE: Clearing project data for:', projectId)
      set(state => {
        const newProjectData = { ...state.projectData }
        delete newProjectData[projectId]
        return { projectData: newProjectData }
      })
    },
    
    switchToProject: (projectId: string) => {
      console.log('🏪 STORE: Switching to project:', projectId)
      
      // AGGRESSIVE DEBUGGING: Log current state
      const currentState = get()
      console.log('🏪 BEFORE SWITCH:', {
        currentProjectId: currentState.currentProjectId,
        currentNodeCount: Object.keys(currentState.nodes).length,
        projectDataKeys: Object.keys(currentState.projectData),
        targetProjectExists: !!currentState.projectData[projectId]
      })
      
      const projectData = get().getProjectData(projectId)
      
      if (projectData) {
        console.log('🔄 Found project data, switching display:', {
          projectId,
          nodeCount: Object.keys(projectData.nodes).length,
          lastUpdated: new Date(projectData.lastUpdated).toISOString(),
          overallGoal: projectData.overallProjectGoal?.substring(0, 50)
        })
        
        // CRITICAL FIX: Update current project FIRST to prevent race conditions
        set({ currentProjectId: projectId })
        
        // CRITICAL FIX: Create completely new API response object to force re-render
        const apiResponse: APIResponse = {
          all_nodes: { ...projectData.nodes }, // Shallow copy to ensure new reference
          graphs: { ...projectData.graphs },
          overall_project_goal: projectData.overallProjectGoal,
          project_id: projectId, // Include project ID for consistency
          timestamp: new Date().toISOString() // Add timestamp to force updates
        }
        
        // Update display with project data
        get().setData(apiResponse)
        
        // AGGRESSIVE DEBUGGING: Verify the switch worked
        setTimeout(() => {
          const afterState = get()
          console.log('✅ AFTER SWITCH VERIFICATION:', {
            currentProjectId: afterState.currentProjectId,
            displayNodeCount: Object.keys(afterState.nodes).length,
            switchSuccessful: afterState.currentProjectId === projectId,
            nodeCountMatch: Object.keys(afterState.nodes).length === Object.keys(projectData.nodes).length
          })
          
          if (afterState.currentProjectId !== projectId) {
            console.error('🚨 CRITICAL: Project switch failed - current project mismatch!')
          }
          if (Object.keys(afterState.nodes).length !== Object.keys(projectData.nodes).length) {
            console.error('🚨 CRITICAL: Project switch failed - node count mismatch!')
          }
        }, 100)
        
        console.log('✅ STORE: Switched to project:', projectId, 'with', Object.keys(projectData.nodes).length, 'nodes')
      } else {
        console.warn('⚠️ STORE: No data found for project:', projectId, 'setting as current anyway')
        set({ currentProjectId: projectId })
        
        // Try to load from localStorage backup
        try {
          const backupData = localStorage.getItem(`project_${projectId}_backup`)
          if (backupData) {
            const parsedData = JSON.parse(backupData)
            console.log('🔄 Restored project from localStorage backup:', projectId)
            get().setProjectData(projectId, parsedData)
            get().switchToProject(projectId) // Recursive call with data now available
            return
          }
        } catch (error) {
          console.warn('Failed to restore from localStorage:', error)
        }
        
        // Clear display if no data available
        get().setData({
          all_nodes: {},
          graphs: {},
          overall_project_goal: `Loading project ${projectId}...`
        })
      }
    },
    
    setConnectionStatus: (status: boolean) => {
      const currentRequest = get().hitlRequest
      console.log('🔌 Store: Connection status changed:', status)
      
      // Keep HITL request even when connection drops
      if (!status && currentRequest) {
        console.log('🔒 Preserving HITL request during connection drop')
      }
      
      set({ isConnected: status })
    },
    
    setLoading: (loading: boolean) => {
      console.log('⏳ Store: Loading state changed:', loading)
      set({ isLoading: loading })
    },
    
    selectNode: (nodeId?: string) => set({ selectedNodeId: nodeId }),
    
    toggleContextFlow: () => set((state) => ({ 
      showContextFlow: !state.showContextFlow 
    })),
    
    // Filter Actions
    updateFilters: (newFilters: Partial<GraphFilters>) => {
      set((state) => ({
        filters: { ...state.filters, ...newFilters }
      }))
    },
    
    resetFilters: () => {
      set({ filters: defaultFilters })
    },
    
    toggleFilterPanel: () => {
      set((state) => ({ isFilterPanelOpen: !state.isFilterPanelOpen }))
    },
    
    setSearchTerm: (term: string) => {
      set((state) => ({
        filters: { ...state.filters, searchTerm: term }
      }))
    },
    
    // Quick Filter Actions
    showActiveNodes: () => {
      set((state) => ({
        filters: { ...state.filters, statuses: ['RUNNING', 'READY'] }
      }))
    },
    
    showProblematicNodes: () => {
      set((state) => ({
        filters: { ...state.filters, statuses: ['FAILED', 'NEEDS_REPLAN'] }
      }))
    },
    
    showCompletedNodes: () => {
      set((state) => ({
        filters: { ...state.filters, statuses: ['DONE'] }
      }))
    },
    
    showCurrentLayer: () => {
      const { nodes, selectedNodeId } = get()
      if (selectedNodeId && nodes[selectedNodeId]) {
        const selectedLayer = nodes[selectedNodeId].layer
        set((state) => ({
          filters: { ...state.filters, layers: [selectedLayer] }
        }))
      }
    },
    
    // Context Flow Actions
    setContextFlowMode: (mode) => {
      set({ contextFlowMode: mode })
      // Auto-set focus to selected node when switching to a highlighting mode
      if (mode !== 'none' && !get().focusNodeId && get().selectedNodeId) {
        set({ focusNodeId: get().selectedNodeId })
      }
    },
    
    setFocusNode: (nodeId) => set({ focusNodeId: nodeId }),
    
    zoomToSubtree: (nodeId) => {
      console.log('Zooming to subtree:', nodeId)
      set({ focusNodeId: nodeId, contextFlowMode: 'subtree' })
    },
    
    // Multi-Selection Actions
    toggleNodeSelection: (nodeId: string, isMultiSelect = false) => {
      set((state) => {
        const newSelectedIds = new Set(state.selectedNodeIds)
        
        if (isMultiSelect) {
          // Multi-select mode: toggle the clicked node
          if (newSelectedIds.has(nodeId)) {
            newSelectedIds.delete(nodeId)
          } else {
            newSelectedIds.add(nodeId)
          }
          
          return {
            selectedNodeIds: newSelectedIds,
            selectedNodeId: newSelectedIds.size === 1 ? Array.from(newSelectedIds)[0] : undefined,
            isMultiSelectMode: newSelectedIds.size > 1
          }
        } else {
          // Single select mode: replace selection
          const wasSelected = newSelectedIds.has(nodeId)
          newSelectedIds.clear()
          
          if (!wasSelected) {
            newSelectedIds.add(nodeId)
          }
          
          return {
            selectedNodeIds: newSelectedIds,
            selectedNodeId: newSelectedIds.size === 1 ? nodeId : undefined,
            isMultiSelectMode: false
          }
        }
      })
    },
    
    selectAllNodes: () => {
      const filteredNodes = get().getFilteredNodes()
      const allNodeIds = new Set(Object.keys(filteredNodes))
      
      set({
        selectedNodeIds: allNodeIds,
        selectedNodeId: undefined,
        isMultiSelectMode: allNodeIds.size > 1
      })
    },
    
    selectFilteredNodes: () => {
      const filteredNodes = get().getFilteredNodes()
      const filteredNodeIds = new Set(Object.keys(filteredNodes))
      
      set({
        selectedNodeIds: filteredNodeIds,
        selectedNodeId: undefined,
        isMultiSelectMode: filteredNodeIds.size > 1
      })
    },
    
    clearSelection: () => {
      set({
        selectedNodeIds: new Set(),
        selectedNodeId: undefined,
        isMultiSelectMode: false,
        isComparisonPanelOpen: false
      })
    },
    
    invertSelection: () => {
      const { selectedNodeIds, getFilteredNodes } = get()
      const filteredNodes = getFilteredNodes()
      const allNodeIds = new Set(Object.keys(filteredNodes))
      const newSelection = new Set<string>()
      
      allNodeIds.forEach(id => {
        if (!selectedNodeIds.has(id)) {
          newSelection.add(id)
        }
      })
      
      set({
        selectedNodeIds: newSelection,
        selectedNodeId: newSelection.size === 1 ? Array.from(newSelection)[0] : undefined,
        isMultiSelectMode: newSelection.size > 1
      })
    },
    
    setMultiSelectMode: (enabled: boolean) => {
      if (!enabled) {
        // When disabling multi-select, keep only the first selected node
        const { selectedNodeIds } = get()
        const firstSelected = Array.from(selectedNodeIds)[0]
        
        set({
          selectedNodeIds: firstSelected ? new Set([firstSelected]) : new Set(),
          selectedNodeId: firstSelected,
          isMultiSelectMode: false
        })
      } else {
        set({ isMultiSelectMode: enabled })
      }
    },
    
    setComparisonView: (view) => set({ comparisonView: view }),
    
    toggleComparisonPanel: () => {
      set((state) => ({ isComparisonPanelOpen: !state.isComparisonPanelOpen }))
    },
    
    // Tool Calls Modal Actions
    openToolCallsModal: () => set({ isToolCallsModalOpen: true }),
    
    closeToolCallsModal: () => set({ isToolCallsModalOpen: false }),
    
    // Computed Properties
    getFilteredNodes: () => {
      const { nodes, filters } = get()
      const { statuses, taskTypes, nodeTypes, layers, agentNames, searchTerm, showOnlySelected } = filters
      const { selectedNodeId } = get()
      
      return Object.fromEntries(
        Object.entries(nodes).filter(([id, node]) => {
          // Status filter
          if (statuses.length > 0 && !statuses.includes(node.status)) {
            return false
          }
          
          // Task type filter
          if (taskTypes.length > 0 && !taskTypes.includes(node.task_type)) {
            return false
          }
          
          // Node type filter
          if (nodeTypes.length > 0 && !nodeTypes.includes(node.node_type)) {
            return false
          }
          
          // Layer filter
          if (layers.length > 0 && !layers.includes(node.layer)) {
            return false
          }
          
          // Agent name filter
          if (agentNames.length > 0 && node.agent_name && !agentNames.includes(node.agent_name)) {
            return false
          }
          
          // Show only selected filter
          if (showOnlySelected && id !== selectedNodeId) {
            return false
          }
          
          // Search term filter
          if (searchTerm.trim()) {
            const term = searchTerm.toLowerCase()
            const searchableText = [
              node.goal,
              node.task_type,
              node.agent_name,
              node.output_summary,
              JSON.stringify(node.full_result)
            ].filter(Boolean).join(' ').toLowerCase()
            
            if (!searchableText.includes(term)) {
              return false
            }
          }
          
          return true
        })
      )
    },
    
    getAvailableFilters: () => {
      const { nodes } = get()
      const nodeValues = Object.values(nodes)
      
      return {
        statuses: [...new Set(nodeValues.map(n => n.status))].sort(),
        taskTypes: [...new Set(nodeValues.map(n => n.task_type))].sort(),
        nodeTypes: [...new Set(nodeValues.map(n => n.node_type))].sort() as ('PLAN' | 'EXECUTE')[],
        layers: [...new Set(nodeValues.map(n => n.layer))].sort((a, b) => a - b),
        agentNames: [...new Set(nodeValues.map(n => n.agent_name).filter(Boolean))].sort() as string[]
      }
    },
    
    getSelectedNodes: () => {
      const { nodes, selectedNodeIds } = get()
      return Array.from(selectedNodeIds).map(id => nodes[id]).filter(Boolean)
    },
    
    getSelectionStats: () => {
      const selectedNodes = get().getSelectedNodes()
      
      const stats = {
        total: selectedNodes.length,
        byStatus: {} as Record<string, number>,
        byTaskType: {} as Record<string, number>,
        byLayer: {} as Record<number, number>,
        avgExecutionTime: 0,
        successRate: 0
      }
      
      if (selectedNodes.length === 0) return stats
      
      // Calculate statistics
      let totalExecutionTime = 0
      let nodesWithExecutionTime = 0
      let successCount = 0
      
      selectedNodes.forEach(node => {
        // Status counts
        stats.byStatus[node.status] = (stats.byStatus[node.status] || 0) + 1
        
        // Task type counts
        stats.byTaskType[node.task_type] = (stats.byTaskType[node.task_type] || 0) + 1
        
        // Layer counts
        stats.byLayer[node.layer] = (stats.byLayer[node.layer] || 0) + 1
        
        // Execution time calculation
        if (node.timestamp_created && node.timestamp_completed) {
          const created = new Date(node.timestamp_created).getTime()
          const completed = new Date(node.timestamp_completed).getTime()
          totalExecutionTime += completed - created
          nodesWithExecutionTime++
        }
        
        // Success rate
        if (node.status === 'DONE') {
          successCount++
        }
      })
      
      stats.avgExecutionTime = nodesWithExecutionTime > 0 ? totalExecutionTime / nodesWithExecutionTime : 0
      stats.successRate = selectedNodes.length > 0 ? (successCount / selectedNodes.length) * 100 : 0
      
      return stats
    },
    
    // HITL Actions with AGGRESSIVE DEBUGGING
    setHITLRequest: (request: HITLRequest | null) => {
      const current = get().hitlRequest
      const timestamp = new Date().toISOString()
      
      console.log('🏪 Store: Setting HITL request:', {
        timestamp,
        previous: current?.request_id || 'none',
        new: request?.request_id || 'none',
        checkpoint: request?.checkpoint_name || 'none',
        attempt: request?.current_attempt || 'none',
        fullRequest: request
      })
      
      // AGGRESSIVE DEBUGGING: Validate the request
      if (request) {
        const validationErrors = []
        if (!request.request_id) validationErrors.push('missing request_id')
        if (!request.checkpoint_name) validationErrors.push('missing checkpoint_name')
        if (!request.node_id) validationErrors.push('missing node_id')
        
        if (validationErrors.length > 0) {
          console.error('🚨 Store: Invalid HITL request:', {
            errors: validationErrors,
            request
          })
        } else {
          console.log('✅ Store: HITL request validation passed')
        }
      }
      
      // Set the state
      const newState = { 
        hitlRequest: request,
        currentHITLRequest: request || undefined,
        isHITLModalOpen: request !== null
      }
      
      console.log('🏪 Store: Setting new HITL state:', newState)
      set(newState)
      
      // AGGRESSIVE DEBUGGING: Verify the state was set
      setTimeout(() => {
        const verifyState = get()
        console.log('🔍 Store: HITL state verification:', {
          timestamp: new Date().toISOString(),
          hitlRequest: verifyState.hitlRequest,
          currentHITLRequest: verifyState.currentHITLRequest,
          isHITLModalOpen: verifyState.isHITLModalOpen,
          requestIdMatch: verifyState.hitlRequest?.request_id === request?.request_id,
          stateSetCorrectly: !!verifyState.hitlRequest === !!request
        })
        
        if (request && !verifyState.hitlRequest) {
          console.error('🚨 CRITICAL: HITL request was not persisted in store!')
        } else if (request && verifyState.hitlRequest?.request_id !== request.request_id) {
          console.error('🚨 CRITICAL: HITL request ID mismatch in store!')
        }
      }, 50)
    },

    clearHITLRequest: () => {
      const timestamp = new Date().toISOString()
      console.log('🏪 Store: Explicitly clearing HITL request', { timestamp })
      
      const newState = { 
        hitlRequest: null,
        currentHITLRequest: undefined,
        isHITLModalOpen: false
      }
      
      console.log('🏪 Store: Setting cleared HITL state:', newState)
      set(newState)
      
      // Verify the clear worked
      setTimeout(() => {
        const verifyState = get()
        console.log('🔍 Store: HITL clear verification:', {
          timestamp: new Date().toISOString(),
          hitlRequest: verifyState.hitlRequest,
          currentHITLRequest: verifyState.currentHITLRequest,
          isHITLModalOpen: verifyState.isHITLModalOpen,
          clearedCorrectly: !verifyState.hitlRequest && !verifyState.currentHITLRequest && !verifyState.isHITLModalOpen
        })
      }, 50)
    },
    
    respondToHITL: (response: HITLResponse) => {
      const { currentHITLRequest } = get()
      if (currentHITLRequest) {
        console.log('HITL Response:', response)
      }
      set({
        currentHITLRequest: undefined,
        isHITLModalOpen: false,
      })
    },
    
    closeHITLModal: () => set({
      currentHITLRequest: undefined,
      isHITLModalOpen: false,
    }),
    
    // HITL Logs Actions
    addHITLLog: (log: HITLLog) => {
      set((state) => ({
        hitlLogs: [...state.hitlLogs, log].slice(-20) // Keep last 20 logs
      }))
    },
    
    clearHITLLogs: () => {
      set({ hitlLogs: [] })
    },
    
    // New properties
    hitlRequest: null,
  }))
)

// AGGRESSIVE DEBUGGING: Add store state monitoring
if (typeof window !== 'undefined' && window) {
  let lastHITLState = null
  
  useTaskGraphStore.subscribe((state) => {
    const currentHITLState = {
      hitlRequest: state.hitlRequest,
      currentHITLRequest: state.currentHITLRequest,
      isHITLModalOpen: state.isHITLModalOpen
    }
    
    // Only log if HITL state actually changed
    if (JSON.stringify(currentHITLState) !== JSON.stringify(lastHITLState)) {
      console.log('🏪 Store: HITL state changed:', {
        timestamp: new Date().toISOString(),
        previous: lastHITLState,
        current: currentHITLState,
        hasRequest: !!currentHITLState.hitlRequest,
        modalShouldBeOpen: !!currentHITLState.hitlRequest
      })
      lastHITLState = currentHITLState
    }
  })
  
  // Add global debugging functions
  const globalWindow = window as any
  
  globalWindow.getHITLStoreState = () => {
    const state = useTaskGraphStore.getState()
    return {
      hitlRequest: state.hitlRequest,
      currentHITLRequest: state.currentHITLRequest,
      isHITLModalOpen: state.isHITLModalOpen,
      hitlLogs: state.hitlLogs
    }
  }
  
  globalWindow.triggerTestHITLFromStore = () => {
    const testRequest = {
      request_id: 'store-test-' + Date.now(),
      checkpoint_name: 'StoreTestCheckpoint',
      context_message: 'This is a test HITL request triggered from store',
      data_for_review: { test: true, source: 'store' },
      node_id: 'store-test-node',
      current_attempt: 1,
      timestamp: new Date().toISOString()
    }
    
    console.log('🧪 Triggering test HITL from store:', testRequest)
    useTaskGraphStore.getState().setHITLRequest(testRequest)
  }
  
  globalWindow.getHITLState = globalWindow.getHITLStoreState
  
  // NEW: Add project debugging functions
  globalWindow.getProjectStoreState = () => {
    const state = useTaskGraphStore.getState()
    return {
      currentProjectId: state.currentProjectId,
      projectData: Object.keys(state.projectData).reduce((acc, projectId) => {
        const data = state.projectData[projectId]
        acc[projectId] = {
          nodeCount: Object.keys(data.nodes).length,
          goal: data.overallProjectGoal,
          lastUpdated: new Date(data.lastUpdated).toISOString()
        }
        return acc
      }, {} as Record<string, any>),
      displayNodeCount: Object.keys(state.nodes).length,
      displayGoal: state.overallProjectGoal
    }
  }
  
  globalWindow.switchToProject = (projectId: string) => {
    console.log('🧪 Switching to project via debug:', projectId)
    useTaskGraphStore.getState().switchToProject(projectId)
  }
  
  // NEW: Add more comprehensive debug functions for testing
  globalWindow.testProjectData = (projectId: string, data: any) => {
    console.log('🧪 Testing setProjectData for:', projectId)
    useTaskGraphStore.getState().setProjectData(projectId, data)
    return useTaskGraphStore.getState().getProjectData(projectId)
  }
  
  globalWindow.testProjectSwitch = (projectId: string) => {
    console.log('🧪 Testing complete project switch for:', projectId)
    const store = useTaskGraphStore.getState()
    
    // Get data before switch
    const beforeSwitch = {
      currentProjectId: store.currentProjectId,
      displayNodeCount: Object.keys(store.nodes).length,
      displayGoal: store.overallProjectGoal
    }
    
    // Switch project
    store.switchToProject(projectId)
    
    // Get data after switch
    const afterSwitch = {
      currentProjectId: store.currentProjectId,
      displayNodeCount: Object.keys(store.nodes).length,
      displayGoal: store.overallProjectGoal
    }
    
    return { beforeSwitch, afterSwitch }
  }
  
  globalWindow.getAllProjectData = () => {
    const store = useTaskGraphStore.getState()
    return {
      currentProjectId: store.currentProjectId,
      allProjects: Object.keys(store.projectData),
      projectDetails: Object.keys(store.projectData).reduce((acc, projectId) => {
        const data = store.projectData[projectId]
        acc[projectId] = {
          nodeCount: Object.keys(data.nodes).length,
          goal: data.overallProjectGoal,
          lastUpdated: new Date(data.lastUpdated).toISOString()
        }
        return acc
      }, {} as Record<string, any>)
    }
  }
} 