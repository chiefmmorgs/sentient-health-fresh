import React, { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { webSocketService } from '@/services/websocketService'
import { Clock, CheckCircle, XCircle, AlertCircle, Eye, Code, MessageSquare, Settings } from 'lucide-react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'

interface ProcessingStage {
  stage_name: string
  stage_id: string
  started_at: string
  completed_at?: string
  status: 'running' | 'completed' | 'failed'
  agent_name?: string
  adapter_name?: string
  model_info?: any
  system_prompt?: string
  user_input?: string
  llm_response?: string
  input_context?: any
  processing_parameters?: any
  output_data?: any
  error_message?: string
  error_details?: any
  duration_ms?: number
  additional_data?: any
  llm_input_messages?: Array<{role: string, content: string}>
}

interface NodeTrace {
  node_id: string
  node_goal: string
  trace_id: string
  created_at: string
  stages: ProcessingStage[]
  metadata: any
}

interface NodeTracingModalProps {
  isOpen: boolean
  onClose: () => void
  nodeId: string
  nodeGoal: string
}

const NodeTracingModal: React.FC<NodeTracingModalProps> = ({
  isOpen,
  onClose,
  nodeId,
  nodeGoal
}) => {
  const [trace, setTrace] = useState<NodeTrace | null>(null)
  const [selectedStage, setSelectedStage] = useState<ProcessingStage | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('input')

  useEffect(() => {
    if (isOpen && nodeId) {
      fetchNodeTrace()
    }
  }, [isOpen, nodeId])

  const fetchNodeTrace = async () => {
    setLoading(true)
    setError(null)
    
    try {
      // Get current project ID for context
      const currentProject = useTaskGraphStore.getState().currentProjectId
      
      // Get the socket instance
      const socket = webSocketService.getSocket()
      
      if (!socket || !webSocketService.isConnected()) {
        setError('WebSocket not connected')
        setLoading(false)
        return
      }
      
      // Set up listeners first
      const handleTraceData = (data: any) => {
        if (data.node_id === nodeId) {
          if (data.trace) {
            setTrace(data.trace)
          } else {
            // Enhanced error message
            const message = data.message || 'No trace found for this node'
            const suggestions = data.suggestions || []
            
            let errorMsg = message
            if (suggestions.length > 0) {
              errorMsg += '\n\nSuggestions:\n' + suggestions.map(s => `• ${s}`).join('\n')
            }
            
            setError(errorMsg)
          }
          setLoading(false)
          
          // Clean up listeners
          socket.off('node_trace_data', handleTraceData)
          socket.off('node_trace_error', handleTraceError)
        }
      }
      
      const handleTraceError = (data: any) => {
        setError(data.error || 'Failed to fetch trace data')
        setLoading(false)
        
        // Clean up listeners
        socket.off('node_trace_data', handleTraceData)
        socket.off('node_trace_error', handleTraceError)
      }
      
      // Set up listeners
      socket.on('node_trace_data', handleTraceData)
      socket.on('node_trace_error', handleTraceError)
      
      // Request trace data with project context
      socket.emit('request_node_trace', { 
        node_id: nodeId,
        project_id: currentProject
      })
      
      // Set a timeout to prevent hanging
      setTimeout(() => {
        if (loading) {
          setError('Request timed out')
          setLoading(false)
          socket.off('node_trace_data', handleTraceData)
          socket.off('node_trace_error', handleTraceError)
        }
      }, 10000)
      
    } catch (error) {
      console.error('Error fetching trace:', error)
      setError('Failed to request trace data')
      setLoading(false)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />
      case 'running':
        return <AlertCircle className="w-4 h-4 text-yellow-500" />
      default:
        return <Clock className="w-4 h-4 text-gray-500" />
    }
  }

  const formatDuration = (ms?: number) => {
    if (!ms) return 'N/A'
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString()
  }

  const getDeduplicatedStages = (stages: ProcessingStage[]): ProcessingStage[] => {
    const stageMap = new Map<string, ProcessingStage>()
    
    // Process stages in order, keeping the most recent completed stage for each stage_name
    for (const stage of stages) {
      const existing = stageMap.get(stage.stage_name)
      
      if (!existing) {
        // First occurrence of this stage name
        stageMap.set(stage.stage_name, stage)
      } else {
        // If we have a completed stage, prefer it over running stages
        if (stage.status === 'completed' && existing.status === 'running') {
          stageMap.set(stage.stage_name, stage)
        } else if (stage.status === 'completed' && existing.status === 'completed') {
          // If both are completed, keep the more recent one
          if (new Date(stage.started_at) > new Date(existing.started_at)) {
            stageMap.set(stage.stage_name, stage)
          }
        }
        // If existing is completed and new is running, keep existing
      }
    }
    
    // Return stages in original order, but deduplicated
    return Array.from(stageMap.values()).sort((a, b) => 
      new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
    )
  }

  const renderStageDetails = (stage: ProcessingStage) => {
    return (
      <div className="space-y-4">
        <div className="border-b pb-2">
          <h3 className="text-lg font-semibold capitalize">{stage.stage_name}</h3>
          <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
            <span>Status: {stage.status}</span>
            {stage.agent_name && <span>Agent: {stage.agent_name}</span>}
            {stage.duration_ms && <span>Duration: {formatDuration(stage.duration_ms)}</span>}
          </div>
        </div>
        
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="input">Input</TabsTrigger>
            <TabsTrigger value="output">Output</TabsTrigger>
            <TabsTrigger value="context">Context</TabsTrigger>
            <TabsTrigger value="config">Config</TabsTrigger>
          </TabsList>
          
          <TabsContent value="input" className="space-y-3 mt-4">
            {/* Check if we have llm_input_messages in additional_data */}
            {stage.additional_data?.llm_input_messages ? (
              <div>
                <h4 className="font-medium mb-2">LLM Input Messages:</h4>
                <div className="space-y-3">
                  {stage.additional_data.llm_input_messages.map((message: any, index: number) => (
                    <div key={index} className="border rounded p-3 bg-muted/50">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-semibold uppercase text-muted-foreground">
                          {message.role}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          ({message.content?.length?.toLocaleString() || 0} characters)
                        </span>
                      </div>
                      <ScrollArea className="h-64 w-full">
                        <pre className="text-xs whitespace-pre-wrap">{message.content}</pre>
                      </ScrollArea>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              /* Fall back to showing system_prompt and user_input separately */
              <>
                {stage.system_prompt ? (
                  <div>
                    <h4 className="font-medium mb-2">System Prompt:</h4>
                    <ScrollArea className="h-48 w-full rounded border p-3 bg-muted/50">
                      <pre className="text-xs whitespace-pre-wrap">{stage.system_prompt}</pre>
                    </ScrollArea>
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground p-4 text-center border rounded">
                    No system prompt data available
                  </div>
                )}
                
                {stage.user_input ? (
                  <div>
                    <h4 className="font-medium mb-2">User Input:</h4>
                    <ScrollArea className="h-48 w-full rounded border p-3 bg-muted/50">
                      <pre className="text-xs whitespace-pre-wrap">{stage.user_input}</pre>
                    </ScrollArea>
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground p-4 text-center border rounded">
                    No user input data available
                  </div>
                )}
              </>
            )}
          </TabsContent>
          
          <TabsContent value="output" className="space-y-3 mt-4">
            {stage.llm_response ? (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium">LLM Response:</h4>
                  <div className="flex gap-2">
                    <span className="text-xs text-muted-foreground">
                      {stage.llm_response.length.toLocaleString()} characters
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const newWindow = window.open('', '_blank')
                        if (newWindow) {
                          newWindow.document.write(`
                            <html>
                              <head>
                                <title>LLM Response - ${stage.stage_name}</title>
                                <style>
                                  body { 
                                    font-family: 'Courier New', monospace; 
                                    white-space: pre-wrap; 
                                    padding: 20px; 
                                    line-height: 1.4;
                                    max-width: 1200px;
                                    margin: 0 auto;
                                  }
                                </style>
                              </head>
                              <body>${stage.llm_response}</body>
                            </html>
                          `)
                        }
                      }}
                    >
                      Open in New Window
                    </Button>
                  </div>
                </div>
                <div className="border rounded bg-muted/50">
                  <ScrollArea className="h-[50vh] w-full p-3">
                    <pre className="text-xs whitespace-pre-wrap font-mono leading-relaxed">
                      {stage.llm_response}
                    </pre>
                  </ScrollArea>
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground p-4 text-center border rounded">
                No LLM response data available
              </div>
            )}
            
            {stage.output_data ? (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium">Output Data:</h4>
                  <div className="flex gap-2">
                    <span className="text-xs text-muted-foreground">
                      {(typeof stage.output_data === 'string' ? stage.output_data : JSON.stringify(stage.output_data, null, 2)).length.toLocaleString()} characters
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const content = typeof stage.output_data === 'string' ? stage.output_data : JSON.stringify(stage.output_data, null, 2)
                        const newWindow = window.open('', '_blank')
                        if (newWindow) {
                          newWindow.document.write(`
                            <html>
                              <head>
                                <title>Output Data - ${stage.stage_name}</title>
                                <style>
                                  body { 
                                    font-family: 'Courier New', monospace; 
                                    white-space: pre-wrap; 
                                    padding: 20px; 
                                    line-height: 1.4;
                                    max-width: 1200px;
                                    margin: 0 auto;
                                  }
                                </style>
                              </head>
                              <body>${content}</body>
                            </html>
                          `)
                        }
                      }}
                    >
                      Open in New Window
                    </Button>
                  </div>
                </div>
                <div className="border rounded bg-muted/50">
                  <ScrollArea className="h-[50vh] w-full p-3">
                    <pre className="text-xs whitespace-pre-wrap font-mono leading-relaxed">
                      {typeof stage.output_data === 'string' ? stage.output_data : JSON.stringify(stage.output_data, null, 2)}
                    </pre>
                  </ScrollArea>
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground p-4 text-center border rounded">
                No output data available
              </div>
            )}
            
            {stage.error_message && (
              <div>
                <h4 className="font-medium mb-2 text-red-600">Error:</h4>
                <ScrollArea className="max-h-32 w-full rounded border p-3 bg-red-50">
                  <pre className="text-xs whitespace-pre-wrap text-red-700">{stage.error_message}</pre>
                </ScrollArea>
              </div>
            )}
          </TabsContent>
          
          <TabsContent value="context" className="mt-4">
            <div>
              <h4 className="font-medium mb-2">Input Context:</h4>
              <ScrollArea className="h-[50vh] w-full rounded border p-3 bg-muted/50">
                <pre className="text-xs whitespace-pre-wrap font-mono">
                  {stage.input_context ? JSON.stringify(stage.input_context, null, 2) : 'No context data available'}
                </pre>
              </ScrollArea>
            </div>
          </TabsContent>
          
          <TabsContent value="config" className="space-y-3 mt-4">
            {stage.model_info ? (
              <div>
                <h4 className="font-medium mb-2">Model Info:</h4>
                <ScrollArea className="max-h-48 w-full rounded border p-3 bg-muted/50">
                  <pre className="text-xs whitespace-pre-wrap font-mono">
                    {JSON.stringify(stage.model_info, null, 2)}
                  </pre>
                </ScrollArea>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground p-4 text-center border rounded">
                No model info available
              </div>
            )}
            
            {stage.processing_parameters ? (
              <div>
                <h4 className="font-medium mb-2">Processing Parameters:</h4>
                <ScrollArea className="max-h-48 w-full rounded border p-3 bg-muted/50">
                  <pre className="text-xs whitespace-pre-wrap font-mono">
                    {JSON.stringify(stage.processing_parameters, null, 2)}
                  </pre>
                </ScrollArea>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground p-4 text-center border rounded">
                No processing parameters available
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    )
  }

  // Reset activeTab when selectedStage changes
  useEffect(() => {
    if (selectedStage) {
      setActiveTab('input')
    }
  }, [selectedStage])

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-6xl max-h-[95vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Eye className="w-5 h-5" />
            Stage Tracing: {nodeId}
          </DialogTitle>
          <p className="text-sm text-muted-foreground">
            {nodeGoal}
          </p>
        </DialogHeader>
        
        <div className="flex-1 overflow-auto min-h-[70vh] max-h-[80vh]">
          {loading && (
            <div className="flex items-center justify-center h-32">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
                <p className="text-sm text-muted-foreground">Loading trace data...</p>
              </div>
            </div>
          )}
          
          {error && (
            <div className="flex items-center justify-center h-32">
              <div className="text-center">
                <XCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
                <p className="text-sm text-red-600">{error}</p>
                <Button variant="outline" size="sm" onClick={fetchNodeTrace} className="mt-2">
                  Retry
                </Button>
              </div>
            </div>
          )}
          
          {trace && !loading && (
            <div className="flex h-full gap-4">
              {/* Stages List */}
              <div className="w-1/3 border-r pr-4 flex flex-col">
                <h3 className="font-medium mb-3">Processing Stages</h3>
                <ScrollArea className="flex-1 min-h-0">
                  <div className="space-y-2">
                    {getDeduplicatedStages(trace.stages).map((stage, index) => (
                      <Card 
                        key={stage.stage_id}
                        className={`cursor-pointer transition-colors ${
                          selectedStage?.stage_id === stage.stage_id ? 'ring-2 ring-primary' : ''
                        }`}
                        onClick={() => setSelectedStage(stage)}
                      >
                        <CardHeader className="pb-2">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              {getStatusIcon(stage.status)}
                              <span className="text-sm font-medium capitalize">{stage.stage_name}</span>
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {formatTimestamp(stage.started_at)}
                            </span>
                          </div>
                        </CardHeader>
                        <CardContent className="pt-0">
                          <div className="text-xs text-muted-foreground">
                            {stage.agent_name && <div>Agent: {stage.agent_name}</div>}
                            <div>Duration: {formatDuration(stage.duration_ms)}</div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </ScrollArea>
              </div>
              
              {/* Stage Details */}
              <div className="flex-1 flex flex-col overflow-hidden">
                {selectedStage ? (
                  <ScrollArea className="flex-1 min-h-0">
                    {renderStageDetails(selectedStage)}
                  </ScrollArea>
                ) : (
                  <div className="flex items-center justify-center h-full text-muted-foreground">
                    <div className="text-center">
                      <Eye className="w-12 h-12 mx-auto mb-2 opacity-50" />
                      <p>Select a stage to view details</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
        
        <div className="flex justify-between items-center pt-4 border-t">
          <div className="text-xs text-muted-foreground">
            {trace && `${trace.stages.length} stages • Created: ${formatTimestamp(trace.created_at)}`}
          </div>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default NodeTracingModal 