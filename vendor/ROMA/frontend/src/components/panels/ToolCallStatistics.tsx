import React from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { 
  Clock,
  Zap, 
  Database,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  Timer,
  Cpu,
  HardDrive
} from 'lucide-react'
import { ToolCall } from '@/types'

interface ToolCallStatisticsProps {
  toolCalls: ToolCall[]
}

export const ToolCallStatistics: React.FC<ToolCallStatisticsProps> = ({ toolCalls }) => {
  if (!toolCalls || toolCalls.length === 0) {
    return null
  }


  // Calculate aggregate statistics
  const stats = {
    totalCalls: toolCalls.length,
    successfulCalls: toolCalls.filter(call => !call.tool_call_error).length,
    failedCalls: toolCalls.filter(call => call.tool_call_error).length,
    totalExecutionTime: toolCalls.reduce((sum, call) => sum + (call.execution_duration_ms || 0), 0),
    totalTokens: toolCalls.reduce((sum, call) => sum + (call.metrics?.total_tokens || 0), 0),
    totalInputTokens: toolCalls.reduce((sum, call) => sum + (call.metrics?.input_tokens || 0), 0),
    totalOutputTokens: toolCalls.reduce((sum, call) => sum + (call.metrics?.output_tokens || 0), 0),
    totalCachedTokens: toolCalls.reduce((sum, call) => sum + (call.metrics?.cached_tokens || 0), 0),
    avgTokensPerSecond: 0,
    avgCacheEfficiency: 0,
    totalResultSize: toolCalls.reduce((sum, call) => sum + (call.result_size_bytes || 0), 0),
    toolkitBreakdown: {} as Record<string, { count: number, category: string, icon: string }>
  }

  // Calculate averages
  const callsWithDuration = toolCalls.filter(call => call.execution_duration_ms && call.execution_duration_ms > 0)
  if (callsWithDuration.length > 0) {
    const avgDuration = stats.totalExecutionTime / callsWithDuration.length / 1000 // Convert to seconds
    if (avgDuration > 0 && stats.totalOutputTokens > 0) {
      stats.avgTokensPerSecond = Math.round((stats.totalOutputTokens / avgDuration) * 100) / 100
    }
  }

  // Calculate average cache efficiency
  const callsWithCacheData = toolCalls.filter(call => 
    call.metrics?.total_tokens && call.metrics.total_tokens > 0
  )
  if (callsWithCacheData.length > 0) {
    const totalCacheEfficiency = callsWithCacheData.reduce((sum, call) => {
      const efficiency = ((call.metrics?.cached_tokens || 0) / (call.metrics?.total_tokens || 1)) * 100
      return sum + efficiency
    }, 0)
    stats.avgCacheEfficiency = Math.round((totalCacheEfficiency / callsWithCacheData.length) * 10) / 10
  }

  // Build toolkit breakdown
  toolCalls.forEach(call => {
    const toolkitKey = call.toolkit_name || call.toolkit_category || 'unknown'
    if (!stats.toolkitBreakdown[toolkitKey]) {
      stats.toolkitBreakdown[toolkitKey] = {
        count: 0,
        category: call.toolkit_category || 'unknown',
        icon: call.toolkit_icon || '🔧'
      }
    }
    stats.toolkitBreakdown[toolkitKey].count++
  })

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`
    return `${Math.round(ms / 100) / 10}s`
  }

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024 * 10) / 10} KB`
    return `${Math.round(bytes / (1024 * 1024) * 10) / 10} MB`
  }

  const successRate = stats.totalCalls > 0 ? Math.round((stats.successfulCalls / stats.totalCalls) * 100) : 0

  return (
    <div className="space-y-4">
      {/* Performance Overview */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-blue-600" />
            Performance Overview
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            {/* Execution Stats */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  Total Time
                </span>
                <span className="font-mono">{formatDuration(stats.totalExecutionTime)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground flex items-center gap-1">
                  <Zap className="w-3 h-3" />
                  Avg Speed
                </span>
                <span className="font-mono">
                  {stats.avgTokensPerSecond > 0 ? `${stats.avgTokensPerSecond} tok/s` : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground flex items-center gap-1">
                  <Database className="w-3 h-3" />
                  Cache Hit
                </span>
                <span className="font-mono">
                  {stats.avgCacheEfficiency > 0 ? `${stats.avgCacheEfficiency}%` : 'N/A'}
                </span>
              </div>
            </div>

            {/* Success Stats */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground flex items-center gap-1">
                  <CheckCircle className="w-3 h-3" />
                  Success Rate
                </span>
                <Badge variant={successRate >= 90 ? 'default' : successRate >= 75 ? 'secondary' : 'destructive'} className="text-xs px-1">
                  {successRate}%
                </Badge>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  Failed
                </span>
                <span className="font-mono text-red-600">{stats.failedCalls}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground flex items-center gap-1">
                  <HardDrive className="w-3 h-3" />
                  Data Size
                </span>
                <span className="font-mono">{formatBytes(stats.totalResultSize)}</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Token Usage */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Cpu className="w-4 h-4 text-green-600" />
            Token Usage
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Input Tokens</span>
                <span className="font-mono">{stats.totalInputTokens.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Output Tokens</span>
                <span className="font-mono">{stats.totalOutputTokens.toLocaleString()}</span>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Cached Tokens</span>
                <span className="font-mono text-blue-600">{stats.totalCachedTokens.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground font-semibold">Total Tokens</span>
                <span className="font-mono font-semibold">{stats.totalTokens.toLocaleString()}</span>
              </div>
            </div>
          </div>
          
          {/* Token usage bar */}
          {stats.totalTokens > 0 && (
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Distribution</span>
                <span>{((stats.totalInputTokens / stats.totalTokens) * 100).toFixed(0)}% input</span>
              </div>
              <div className="h-2 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                <div className="h-full flex">
                  <div 
                    className="bg-blue-500" 
                    style={{ width: `${(stats.totalInputTokens / stats.totalTokens) * 100}%` }}
                  />
                  <div 
                    className="bg-green-500" 
                    style={{ width: `${(stats.totalOutputTokens / stats.totalTokens) * 100}%` }}
                  />
                  <div 
                    className="bg-purple-500" 
                    style={{ width: `${(stats.totalCachedTokens / stats.totalTokens) * 100}%` }}
                  />
                </div>
              </div>
              <div className="flex items-center gap-4 text-xs">
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 bg-blue-500 rounded-full" />
                  <span>Input</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 bg-green-500 rounded-full" />
                  <span>Output</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 bg-purple-500 rounded-full" />
                  <span>Cached</span>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Toolkit Breakdown */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Timer className="w-4 h-4 text-orange-600" />
            Toolkit Usage
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {Object.entries(stats.toolkitBreakdown)
              .sort(([,a], [,b]) => b.count - a.count)
              .map(([toolkit, data]) => (
                <div key={toolkit} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-base">{data.icon}</span>
                    <span className="capitalize">
                      {toolkit === 'unknown' ? 'General Tools' : toolkit}
                    </span>
                    <Badge variant="outline" className="text-xs px-1">
                      {data.category}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono">{data.count}</span>
                    <div 
                      className="w-12 h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden"
                    >
                      <div 
                        className="h-full bg-orange-500" 
                        style={{ width: `${(data.count / stats.totalCalls) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))
            }
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default ToolCallStatistics