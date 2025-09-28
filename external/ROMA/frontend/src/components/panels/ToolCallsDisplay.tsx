import React, { useState } from 'react'
import { ChevronDown, ChevronRight, Copy, AlertTriangle, CheckCircle, Clock, Zap, Database, HardDrive, Timer } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ToolCall } from '@/types'
import ToolCallStatistics from './ToolCallStatistics'

interface ToolCallsDisplayProps {
  toolCalls: ToolCall[]
}

export const ToolCallsDisplay: React.FC<ToolCallsDisplayProps> = ({ toolCalls }) => {
  const [expandedCalls, setExpandedCalls] = useState<Set<string>>(new Set())
  
  // Safety check for empty or invalid tool calls
  if (!toolCalls || !Array.isArray(toolCalls) || toolCalls.length === 0) {
    return (
      <div className="text-xs text-muted-foreground italic p-2">
        No tool calls available
      </div>
    )
  }
  
  const toggleExpanded = (toolCallId: string) => {
    const newExpanded = new Set(expandedCalls)
    if (newExpanded.has(toolCallId)) {
      newExpanded.delete(toolCallId)
    } else {
      newExpanded.add(toolCallId)
    }
    setExpandedCalls(newExpanded)
  }

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
    } catch (err) {
      // Fallback for older browsers
      const textArea = document.createElement('textarea')
      textArea.value = text
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
    }
  }

  const formatDuration = (ms?: number) => {
    if (!ms) return 'N/A'
    if (ms < 1000) return `${ms}ms`
    return `${Math.round(ms / 100) / 10}s`
  }

  const formatBytes = (bytes?: number) => {
    if (!bytes) return 'N/A'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024 * 10) / 10} KB`
    return `${Math.round(bytes / (1024 * 1024) * 10) / 10} MB`
  }

  return (
    <div className="space-y-4">
      {/* Statistics Overview */}
      <ToolCallStatistics toolCalls={toolCalls} />
      
      {/* Individual Tool Calls */}
      <div className="space-y-3">
        {toolCalls.map((toolCall, index) => {
        const callId = toolCall.tool_call_id || `tool-${index}`
        const isExpanded = expandedCalls.has(callId)
        const hasError = toolCall.tool_call_error
        
        return (
          <div key={callId} className={`border rounded-lg p-3 ${hasError ? 'border-red-200 bg-red-50/30 dark:border-red-800 dark:bg-red-900/20' : 'border-gray-200 bg-gray-50/30 dark:border-gray-700 dark:bg-gray-800/50'}`}>
            {/* Tool Call Header */}
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                {hasError ? (
                  <AlertTriangle className="w-4 h-4 text-red-600" />
                ) : (
                  <CheckCircle className="w-4 h-4 text-green-600" />
                )}
                
                {/* Toolkit Icon */}
                {toolCall.toolkit_icon && (
                  <span className="text-sm">{toolCall.toolkit_icon}</span>
                )}
                
                <span className="font-medium text-sm text-foreground">{toolCall.tool_name}</span>
                
                {/* Toolkit Badges */}
                {toolCall.toolkit_name && (
                  <Badge variant="outline" className="text-xs px-1">
                    {toolCall.toolkit_name}
                  </Badge>
                )}
                {toolCall.toolkit_category && toolCall.toolkit_category !== 'unknown' && (
                  <Badge variant="secondary" className="text-xs px-1">
                    {toolCall.toolkit_category}
                  </Badge>
                )}
                
                {toolCall.created_at && (
                  <span className="text-xs text-muted-foreground">
                    {new Date(
                      // Handle both seconds (< 1e12) and milliseconds (>= 1e12) timestamps
                      toolCall.created_at < 1e12 ? toolCall.created_at * 1000 : toolCall.created_at
                    ).toLocaleTimeString()}
                  </span>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => toggleExpanded(callId)}
                className="h-6 px-2"
              >
                {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              </Button>
            </div>
            
            {/* Quick Stats Row */}
            <div className="flex items-center gap-4 mb-2 text-xs text-muted-foreground">
              {toolCall.execution_duration_ms && (
                <div className="flex items-center gap-1">
                  <Timer className="w-3 h-3" />
                  <span>{formatDuration(toolCall.execution_duration_ms)}</span>
                </div>
              )}
              {toolCall.tokens_per_second && (
                <div className="flex items-center gap-1">
                  <Zap className="w-3 h-3" />
                  <span>{toolCall.tokens_per_second} tok/s</span>
                </div>
              )}
              {toolCall.cache_efficiency_percent !== undefined && toolCall.cache_efficiency_percent > 0 && (
                <div className="flex items-center gap-1">
                  <Database className="w-3 h-3" />
                  <span>{toolCall.cache_efficiency_percent}% cached</span>
                </div>
              )}
              {toolCall.result_size_bytes && (
                <div className="flex items-center gap-1">
                  <HardDrive className="w-3 h-3" />
                  <span>{formatBytes(toolCall.result_size_bytes)}</span>
                  {toolCall.result_truncated && (
                    <Badge variant="outline" className="text-xs px-1">truncated</Badge>
                  )}
                </div>
              )}
            </div>
            
            {/* Expanded Content */}
            {isExpanded && (
              <div className="space-y-3 mt-3 pt-3 border-t border-border">
                {/* Tool Arguments */}
                {toolCall.tool_args && (
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-muted-foreground">Arguments</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          try {
                            copyToClipboard(JSON.stringify(toolCall.tool_args, null, 2))
                          } catch (err) {
                            copyToClipboard(String(toolCall.tool_args))
                          }
                        }}
                        className="h-5 px-1"
                      >
                        <Copy className="w-3 h-3" />
                      </Button>
                    </div>
                    {toolCall.tool_name === 'run_python_code' && toolCall.tool_args && typeof toolCall.tool_args === 'object' && 'code' in toolCall.tool_args ? (
                      <div className="space-y-2">
                        {/* Python Code Block */}
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs text-muted-foreground">Python Code:</span>
                            <Badge variant="secondary" className="text-xs">
                              🐍 Python
                            </Badge>
                          </div>
                          <pre className="text-xs bg-slate-900 text-green-400 p-3 rounded overflow-x-auto border font-mono">
                            <code className="language-python">
                              {String(toolCall.tool_args.code)}
                            </code>
                          </pre>
                        </div>
                        
                        {/* Other Arguments (if any) */}
                        {(() => {
                          const { code, ...otherArgs } = toolCall.tool_args as any
                          if (Object.keys(otherArgs).length > 0) {
                            return (
                              <div>
                                <span className="text-xs text-muted-foreground">Other Arguments:</span>
                                <pre className="text-xs bg-muted p-2 rounded overflow-x-auto text-foreground mt-1">
                                  {JSON.stringify(otherArgs, null, 2)}
                                </pre>
                              </div>
                            )
                          }
                          return null
                        })()}
                      </div>
                    ) : (
                      <pre className="text-xs bg-muted p-2 rounded overflow-x-auto text-foreground">
                        {(() => {
                          try {
                            return JSON.stringify(toolCall.tool_args, null, 2)
                          } catch (err) {
                            return `Error displaying arguments: ${err}`
                          }
                        })()}
                      </pre>
                    )}
                  </div>
                )}
                
                {/* Tool Result */}
                {toolCall.result && (
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-muted-foreground">Result</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyToClipboard(toolCall.result || '')}
                        className="h-5 px-1"
                      >
                        <Copy className="w-3 h-3" />
                      </Button>
                    </div>
                    <div className="text-xs bg-muted p-2 rounded max-h-60 overflow-y-auto">
                      {toolCall.result.length > 2000 ? (
                        <details>
                          <summary className="cursor-pointer text-primary hover:text-primary/80">
                            Show full result ({toolCall.result.length.toLocaleString()} characters)
                          </summary>
                          <pre className="mt-2 whitespace-pre-wrap break-words max-w-full text-foreground">
                            {toolCall.result}
                          </pre>
                        </details>
                      ) : (
                        <pre className="whitespace-pre-wrap break-words max-w-full text-foreground">
                          {toolCall.result}
                        </pre>
                      )}
                    </div>
                  </div>
                )}
                
                {/* Enhanced Metrics */}
                {(toolCall.metrics || toolCall.execution_duration_ms || toolCall.requires_confirmation !== undefined) && (
                  <div className="space-y-3">
                    <span className="text-xs font-medium text-muted-foreground">Performance & Execution Details</span>
                    
                    {/* Token Metrics */}
                    {toolCall.metrics && (
                      <div className="grid grid-cols-3 gap-3 text-xs">
                        <div className="space-y-1">
                          <div className="text-muted-foreground">Token Usage</div>
                          {toolCall.metrics.input_tokens && (
                            <div>Input: <span className="font-medium text-foreground">{toolCall.metrics.input_tokens.toLocaleString()}</span></div>
                          )}
                          {toolCall.metrics.output_tokens && (
                            <div>Output: <span className="font-medium text-foreground">{toolCall.metrics.output_tokens.toLocaleString()}</span></div>
                          )}
                          {toolCall.metrics.cached_tokens && (
                            <div>Cached: <span className="font-medium text-blue-600">{toolCall.metrics.cached_tokens.toLocaleString()}</span></div>
                          )}
                          {toolCall.metrics.total_tokens && (
                            <div>Total: <span className="font-semibold text-foreground">{toolCall.metrics.total_tokens.toLocaleString()}</span></div>
                          )}
                        </div>
                        
                        <div className="space-y-1">
                          <div className="text-muted-foreground">Timing</div>
                          {toolCall.execution_duration_ms && (
                            <div>Duration: <span className="font-medium text-foreground">{formatDuration(toolCall.execution_duration_ms)}</span></div>
                          )}
                          {toolCall.metrics.time_to_first_token && (
                            <div>First Token: <span className="font-medium text-foreground">{Math.round(toolCall.metrics.time_to_first_token * 1000)}ms</span></div>
                          )}
                          {toolCall.tokens_per_second && (
                            <div>Speed: <span className="font-medium text-green-600">{toolCall.tokens_per_second} tok/s</span></div>
                          )}
                          {toolCall.cache_efficiency_percent !== undefined && (
                            <div>Cache: <span className="font-medium text-purple-600">{toolCall.cache_efficiency_percent}%</span></div>
                          )}
                        </div>
                        
                        <div className="space-y-1">
                          <div className="text-muted-foreground">Status</div>
                          {toolCall.requires_confirmation !== undefined && (
                            <div>
                              Confirmation: <span className={`font-medium ${toolCall.requires_confirmation ? 'text-orange-600' : 'text-green-600'}`}>
                                {toolCall.requires_confirmation ? 'Required' : 'Not Required'}
                              </span>
                            </div>
                          )}
                          {toolCall.confirmed !== undefined && toolCall.requires_confirmation && (
                            <div>
                              Confirmed: <span className={`font-medium ${toolCall.confirmed ? 'text-green-600' : 'text-red-600'}`}>
                                {toolCall.confirmed ? 'Yes' : 'No'}
                              </span>
                            </div>
                          )}
                          {toolCall.external_execution_required && (
                            <div>External: <span className="font-medium text-orange-600">Required</span></div>
                          )}
                          {toolCall.result_size_bytes && (
                            <div>Result Size: <span className="font-medium text-foreground">{formatBytes(toolCall.result_size_bytes)}</span></div>
                          )}
                        </div>
                      </div>
                    )}
                    
                    {/* Advanced Metrics */}
                    {toolCall.metrics?.reasoning_tokens && (
                      <div className="pt-2 border-t border-border">
                        <div className="text-xs text-muted-foreground mb-1">Advanced Metrics</div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>Reasoning Tokens: <span className="font-medium text-foreground">{toolCall.metrics.reasoning_tokens.toLocaleString()}</span></div>
                          {toolCall.metrics.cache_write_tokens && (
                            <div>Cache Write: <span className="font-medium text-foreground">{toolCall.metrics.cache_write_tokens.toLocaleString()}</span></div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )
        })}
      </div>
    </div>
  )
}

export default ToolCallsDisplay