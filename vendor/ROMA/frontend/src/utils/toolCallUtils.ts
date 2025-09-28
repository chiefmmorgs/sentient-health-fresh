/**
 * Utility functions for execution time calculations
 */

/**
 * Format execution time difference between two timestamps
 */
export function formatExecutionTime(startTime?: string, endTime?: string): string | null {
  if (!startTime || !endTime) return null
  
  const start = new Date(startTime)
  const end = new Date(endTime)
  const diffMs = end.getTime() - start.getTime()
  
  if (diffMs < 1000) return `${diffMs}ms`
  if (diffMs < 60000) return `${Math.round(diffMs / 1000)}s`
  return `${Math.round(diffMs / 60000)}m ${Math.round((diffMs % 60000) / 1000)}s`
}

/**
 * Calculate total execution time for a node
 */
export function getNodeExecutionTime(node: any): string | null {
  // Try different timestamp fields that might be available
  const startTime = node.timestamp_created || node.created_at
  const endTime = node.timestamp_completed || node.completed_at || 
                  (node.execution_details?.processing_completed)
  
  return formatExecutionTime(startTime, endTime)
}