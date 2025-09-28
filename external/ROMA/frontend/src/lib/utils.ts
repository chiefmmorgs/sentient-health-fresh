import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getStatusColor(status: string): string {
  switch (status?.toLowerCase()) {
    case 'completed':
    case 'success':
      return 'text-green-600 bg-green-50 border-green-200'
    case 'running':
    case 'in_progress':
    case 'executing':
      return 'text-blue-600 bg-blue-50 border-blue-200'
    case 'failed':
    case 'error':
      return 'text-red-600 bg-red-50 border-red-200'
    case 'pending':
    case 'waiting':
      return 'text-yellow-600 bg-yellow-50 border-yellow-200'
    case 'cancelled':
    case 'stopped':
      return 'text-gray-600 bg-gray-50 border-gray-200'
    default:
      return 'text-gray-600 bg-gray-50 border-gray-200'
  }
}

export function truncateText(text: string, maxLength: number = 50): string {
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

export function formatTimestamp(timestamp: string | number): string {
  const date = new Date(timestamp)
  return date.toLocaleString()
}

export function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  
  if (hours > 0) {
    return `${hours}h ${minutes % 60}m ${seconds % 60}s`
  } else if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`
  } else {
    return `${seconds}s`
  }
} 