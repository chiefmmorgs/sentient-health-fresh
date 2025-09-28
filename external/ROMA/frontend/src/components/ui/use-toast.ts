import * as React from "react"

interface ToastProps {
  title?: string
  description?: string
  variant?: "default" | "destructive"
}

interface ToastState {
  toasts: (ToastProps & { id: string })[]
}

let toastCount = 0
const listeners: Array<(state: ToastState) => void> = []
let memoryState: ToastState = { toasts: [] }

function dispatch(action: { type: string; toast?: ToastProps & { id: string } }) {
  switch (action.type) {
    case "ADD_TOAST":
      if (action.toast) {
        memoryState = {
          toasts: [action.toast, ...memoryState.toasts].slice(0, 3) // Keep only 3 toasts
        }
      }
      break
    case "REMOVE_TOAST":
      memoryState = {
        toasts: memoryState.toasts.filter(t => t.id !== action.toast?.id)
      }
      break
  }
  
  listeners.forEach(listener => listener(memoryState))
}

export function toast({ title, description, variant = "default" }: ToastProps) {
  const id = (++toastCount).toString()
  
  dispatch({
    type: "ADD_TOAST",
    toast: { id, title, description, variant }
  })
  
  // Auto remove after 5 seconds
  setTimeout(() => {
    dispatch({
      type: "REMOVE_TOAST",
      toast: { id, title, description, variant }
    })
  }, 5000)
  
  return { id }
}

export function useToast() {
  const [state, setState] = React.useState<ToastState>(memoryState)
  
  React.useEffect(() => {
    listeners.push(setState)
    return () => {
      const index = listeners.indexOf(setState)
      if (index > -1) {
        listeners.splice(index, 1)
      }
    }
  }, [])
  
  return {
    toast,
    toasts: state.toasts
  }
}