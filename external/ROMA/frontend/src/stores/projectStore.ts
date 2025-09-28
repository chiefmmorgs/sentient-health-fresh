import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'

export interface Project {
  id: string
  title: string
  description: string
  created_at: string
  updated_at: string
  status: 'active' | 'completed' | 'failed' | 'paused'
  goal: string
  max_steps: number
  node_count: number
  completion_percentage: number
}

interface ProjectState {
  // Data
  projects: Project[]
  currentProjectId?: string
  isLoading: boolean
  
  // UI State
  isSidebarOpen: boolean
  isCreatingProject: boolean
  
  // Actions
  setProjects: (projects: Project[]) => void
  setCurrentProject: (projectId?: string) => void
  addProject: (project: Project) => void
  updateProject: (projectId: string, updates: Partial<Project>) => void
  removeProject: (projectId: string) => void
  setLoading: (loading: boolean) => void
  setSidebarOpen: (open: boolean) => void
  setCreatingProject: (creating: boolean) => void
  
  // Computed
  getCurrentProject: () => Project | undefined
  getRecentProjects: () => Project[]
}

export const useProjectStore = create<ProjectState>()(
  subscribeWithSelector((set, get) => ({
    // Initial state
    projects: [],
    currentProjectId: undefined,
    isLoading: false,
    isSidebarOpen: true,
    isCreatingProject: false,
    
    // Actions
    setProjects: (projects: Project[]) => {
      set({ projects })
    },
    
    setCurrentProject: (projectId?: string) => {
      set({ currentProjectId: projectId })
    },
    
    addProject: (project: Project) => {
      set(state => ({
        projects: [project, ...state.projects],
        currentProjectId: project.id
      }))
    },
    
    updateProject: (projectId: string, updates: Partial<Project>) => {
      set(state => ({
        projects: state.projects.map(p => 
          p.id === projectId ? { ...p, ...updates } : p
        )
      }))
    },
    
    removeProject: (projectId: string) => {
      set(state => {
        const newProjects = state.projects.filter(p => p.id !== projectId)
        const newCurrentId = state.currentProjectId === projectId 
          ? (newProjects[0]?.id || undefined)
          : state.currentProjectId
        
        return {
          projects: newProjects,
          currentProjectId: newCurrentId
        }
      })
    },
    
    setLoading: (loading: boolean) => {
      set({ isLoading: loading })
    },
    
    setSidebarOpen: (open: boolean) => {
      set({ isSidebarOpen: open })
    },
    
    setCreatingProject: (creating: boolean) => {
      set({ isCreatingProject: creating })
    },
    
    // Computed
    getCurrentProject: () => {
      const { projects, currentProjectId } = get()
      return projects.find(p => p.id === currentProjectId)
    },
    
    getRecentProjects: () => {
      const { projects } = get()
      return projects
        .slice()
        .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
        .slice(0, 10)
    }
  }))
) 