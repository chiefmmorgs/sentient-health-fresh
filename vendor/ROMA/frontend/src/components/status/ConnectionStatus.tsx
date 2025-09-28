import React, { useState, useEffect } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { Wifi, WifiOff } from 'lucide-react'
import { cn } from '@/lib/utils'

const ConnectionStatus: React.FC = () => {
  const { isConnected } = useTaskGraphStore()
  const [showStatus, setShowStatus] = useState(!isConnected)
  const [isAnimating, setIsAnimating] = useState(false)

  useEffect(() => {
    if (!isConnected) {
      setShowStatus(true)
      setIsAnimating(true)
    } else {
      // Delay hiding to show success state
      const timer = setTimeout(() => {
        setShowStatus(false)
      }, 2000)
      return () => clearTimeout(timer)
    }
  }, [isConnected])

  if (!showStatus) return null

  return (
    <div className={cn(
      "fixed bottom-4 right-4 px-4 py-2 rounded-lg flex items-center space-x-2 text-sm shadow-lg transition-all duration-300",
      isConnected 
        ? "bg-green-500 text-white animate-scale-in" 
        : "bg-destructive text-destructive-foreground animate-slide-in",
      isAnimating && "animate-fade-in"
    )}>
      {isConnected ? (
        <>
          <Wifi className="w-4 h-4" />
          <span>Connected</span>
        </>
      ) : (
        <>
          <WifiOff className="w-4 h-4 animate-pulse" />
          <span>Backend Disconnected</span>
        </>
      )}
    </div>
  )
}

export default ConnectionStatus 