import React from 'react'
import { cn } from '@/lib/utils'

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export const Spinner: React.FC<SpinnerProps> = ({ size = 'md', className }) => {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12'
  }

  return (
    <div className={cn('relative', className)}>
      <div className={cn(
        'animate-spin rounded-full border-2 border-muted border-t-primary',
        sizeClasses[size]
      )} />
      <div className={cn(
        'absolute inset-0 rounded-full border-2 border-primary/20 animate-pulse',
        sizeClasses[size]
      )} />
    </div>
  )
}

interface LoadingScreenProps {
  message?: string
  submessage?: string
}

export const LoadingScreen: React.FC<LoadingScreenProps> = ({ message, submessage }) => {
  return (
    <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-muted/20 to-muted/5">
      <div className="text-center animate-fade-in">
        <Spinner size="lg" className="mx-auto mb-6" />
        {message && (
          <h3 className="text-lg font-medium mb-2 animate-slide-in">
            {message}
          </h3>
        )}
        {submessage && (
          <p className="text-muted-foreground animate-slide-in" style={{ animationDelay: '100ms' }}>
            {submessage}
          </p>
        )}
      </div>
    </div>
  )
}