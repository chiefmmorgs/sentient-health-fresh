import React, { createContext, useContext, useEffect } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'

interface TaskGraphContextProps {
  children: React.ReactNode
}

const TaskGraphContext = createContext<null>(null)

export function TaskGraphProvider({ children }: TaskGraphContextProps) {
  return (
    <TaskGraphContext.Provider value={null}>
      {children}
    </TaskGraphContext.Provider>
  )
} 