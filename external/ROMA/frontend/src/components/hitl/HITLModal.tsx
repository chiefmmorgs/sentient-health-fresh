import React, { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { CheckCircle, XCircle, Edit, Clock, AlertTriangle, Loader2, Target, Users, Calendar, FileText, CheckCircle2, ArrowRight, Brain, Zap, MessageSquare, Copy, ChevronDown, ChevronRight, List, Search, PenTool, RefreshCw } from 'lucide-react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { webSocketService } from '@/services/websocketService'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'

interface HITLRequest {
  checkpoint_name: string
  context_message: string
  data_for_review: any
  node_id: string
  current_attempt: number
  request_id: string
  timestamp: string
}

// Plan Viewer Component - Specialized for displaying plans
const PlanViewer: React.FC<{ planData: any; isModified?: boolean }> = ({ planData, isModified = false }) => {
  // Handle both original and modified plan structures
  const getPlanData = () => {
    if (planData?.proposed_plan?.sub_tasks) {
      return planData.proposed_plan
    }
    if (planData?.proposed_modified_plan?.sub_tasks) {
      return planData.proposed_modified_plan
    }
    return null
  }

  const plan = getPlanData()
  
  if (!plan?.sub_tasks) {
    return (
      <Card>
        <CardContent className="p-4">
          <p className="text-muted-foreground italic">No plan data available</p>
        </CardContent>
      </Card>
    )
  }

  const subTasks = plan.sub_tasks

  const getTaskTypeIcon = (taskType: string) => {
    switch (taskType) {
      case 'SEARCH': return <Search className="h-4 w-4 text-blue-600" />
      case 'THINK': return <Brain className="h-4 w-4 text-purple-600" />
      case 'WRITE': return <PenTool className="h-4 w-4 text-green-600" />
      default: return <Target className="h-4 w-4 text-gray-600" />
    }
  }

  const getTaskTypeBadge = (taskType: string) => {
    const variants = {
      'SEARCH': 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300',
      'THINK': 'bg-purple-100 text-purple-800 dark:bg-purple-900/50 dark:text-purple-300',
      'WRITE': 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300'
    }
    return variants[taskType as keyof typeof variants] || 'bg-gray-100 text-gray-800'
  }

  const getNodeTypeBadge = (nodeType: string) => {
    return nodeType === 'PLAN' 
      ? 'bg-orange-100 text-orange-800 dark:bg-orange-900/50 dark:text-orange-300'
      : 'bg-gray-100 text-gray-800 dark:bg-gray-900/50 dark:text-gray-300'
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          {isModified ? <RefreshCw className="h-4 w-4 text-blue-600" /> : <List className="h-4 w-4" />}
          {isModified ? 'Modified Plan' : 'Proposed Plan'} ({subTasks.length} tasks)
          {isModified && (
            <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300">
              Updated
            </Badge>
          )}
        </CardTitle>
        {/* Show modification context for modified plans */}
        {isModified && planData?.original_user_modification_request_for_this_cycle && (
          <div className="mt-2 p-3 bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-200 dark:border-blue-800">
            <p className="text-xs text-blue-800 dark:text-blue-300">
              <strong>Your feedback:</strong> {planData.original_user_modification_request_for_this_cycle}
            </p>
          </div>
        )}
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-4">
          {subTasks.map((task: any, index: number) => (
            <div key={index} className={cn(
              "border rounded-lg p-4 space-y-3",
              isModified && "border-blue-200 bg-blue-50/50 dark:border-blue-800 dark:bg-blue-950/20"
            )}>
              {/* Task Header */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <div className={cn(
                    "flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium",
                    isModified 
                      ? "bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300"
                      : "bg-gray-100 dark:bg-gray-900/50 text-gray-800 dark:text-gray-300"
                  )}>
                    {index + 1}
                  </div>
                  {getTaskTypeIcon(task.task_type)}
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <Badge className={cn("text-xs", getTaskTypeBadge(task.task_type))}>
                    {task.task_type}
                  </Badge>
                  <Badge className={cn("text-xs", getNodeTypeBadge(task.node_type))}>
                    {task.node_type}
                  </Badge>
                </div>
              </div>

              {/* Task Goal */}
              <div>
                <h4 className="font-medium text-sm mb-2">Goal:</h4>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {task.goal}
                </p>
              </div>

              {/* Dependencies */}
              {task.depends_on_indices && task.depends_on_indices.length > 0 && (
                <div>
                  <h4 className="font-medium text-sm mb-2">Dependencies:</h4>
                  <div className="flex gap-1 flex-wrap">
                    {task.depends_on_indices.map((depIndex: number) => (
                      <Badge key={depIndex} variant="outline" className="text-xs">
                        Task {depIndex + 1}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Plan Summary */}
        <div className={cn(
          "mt-6 p-4 rounded-lg",
          isModified 
            ? "bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800"
            : "bg-muted/50"
        )}>
          <h4 className="font-medium text-sm mb-2">Plan Summary:</h4>
          <div className="grid grid-cols-3 gap-4 text-xs">
            <div>
              <span className="text-muted-foreground">Search Tasks:</span>
              <div className="font-medium">{subTasks.filter((t: any) => t.task_type === 'SEARCH').length}</div>
            </div>
            <div>
              <span className="text-muted-foreground">Think Tasks:</span>
              <div className="font-medium">{subTasks.filter((t: any) => t.task_type === 'THINK').length}</div>
            </div>
            <div>
              <span className="text-muted-foreground">Write Tasks:</span>
              <div className="font-medium">{subTasks.filter((t: any) => t.task_type === 'WRITE').length}</div>
            </div>
          </div>
          
          {/* Show replan information for modified plans */}
          {isModified && planData?.replan_attempt_count && (
            <div className="mt-3 pt-3 border-t border-blue-200 dark:border-blue-800">
              <div className="flex items-center gap-2 text-xs text-blue-800 dark:text-blue-300">
                <RefreshCw className="h-3 w-3" />
                <span>Modification attempt {planData.replan_attempt_count}</span>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// Enhanced JSON Viewer Component
const JsonViewer: React.FC<{ data: any; title?: string }> = ({ data, title }) => {
  const [isExpanded, setIsExpanded] = useState(false) // Start collapsed for raw data
  const [copiedPath, setCopiedPath] = useState<string | null>(null)

  const copyToClipboard = (text: string, path: string) => {
    navigator.clipboard.writeText(text)
    setCopiedPath(path)
    setTimeout(() => setCopiedPath(null), 2000)
  }

  // Determine if an item should be expanded by default based on its importance
  const shouldExpandByDefault = (key: string, depth: number) => {
    const importantKeys = ['proposed_plan', 'sub_tasks', 'task_goal']
    return depth < 2 || importantKeys.includes(key)
  }

  const ExpandableItem: React.FC<{ 
    children: React.ReactNode; 
    label: string; 
    defaultExpanded?: boolean;
    itemKey?: string;
    depth?: number;
  }> = ({ children, label, defaultExpanded, itemKey, depth = 0 }) => {
    const [isItemExpanded, setIsItemExpanded] = useState(
      defaultExpanded ?? shouldExpandByDefault(itemKey || '', depth)
    )
    
    return (
      <div className="ml-4">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0"
            onClick={() => setIsItemExpanded(!isItemExpanded)}
          >
            {isItemExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          </Button>
          <span className="text-muted-foreground">{label}</span>
        </div>
        {isItemExpanded && (
          <div className="ml-4 mt-2 space-y-1">
            {children}
          </div>
        )}
      </div>
    )
  }

  const renderValue = (value: any, path: string = '', depth: number = 0, parentKey?: string): React.ReactNode => {
    if (value === null) {
      return <span className="text-muted-foreground italic">null</span>
    }
    
    if (value === undefined) {
      return <span className="text-muted-foreground italic">undefined</span>
    }
    
    if (typeof value === 'boolean') {
      return <span className={cn("font-medium", value ? "text-green-600" : "text-red-600")}>{String(value)}</span>
    }
    
    if (typeof value === 'number') {
      return <span className="text-blue-600 font-medium">{value}</span>
    }
    
    if (typeof value === 'string') {
      return (
        <div className="group relative">
          <span className="text-green-700 dark:text-green-400">"{value}"</span>
          {value.length > 50 && (
            <Button
              variant="ghost"
              size="sm"
              className="ml-2 h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={() => copyToClipboard(value, path)}
            >
              <Copy className="h-3 w-3" />
            </Button>
          )}
        </div>
      )
    }
    
    if (Array.isArray(value)) {
      return (
        <ExpandableItem 
          label={`Array (${value.length} items)`} 
          itemKey={parentKey}
          depth={depth}
        >
          {value.map((item, index) => (
            <div key={index} className="flex gap-2">
              <span className="text-muted-foreground min-w-[2rem]">[{index}]:</span>
              <div className="flex-1">
                {renderValue(item, `${path}[${index}]`, depth + 1, `${parentKey}_${index}`)}
              </div>
            </div>
          ))}
        </ExpandableItem>
      )
    }
    
    if (typeof value === 'object') {
      const keys = Object.keys(value)
      
      return (
        <ExpandableItem 
          label={`Object (${keys.length} properties)`} 
          itemKey={parentKey}
          depth={depth}
        >
          {keys.map((key) => (
            <div key={key} className="flex gap-2">
              <span className="text-purple-600 dark:text-purple-400 font-medium min-w-fit">"{key}":</span>
              <div className="flex-1">
                {renderValue(value[key], `${path}.${key}`, depth + 1, key)}
              </div>
            </div>
          ))}
        </ExpandableItem>
      )
    }
    
    return <span className="text-muted-foreground">{String(value)}</span>
  }

  if (!data) {
    return (
      <Card>
        <CardContent className="p-4">
          <p className="text-muted-foreground italic">No data to display</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <FileText className="h-4 w-4" />
            {title || 'Raw Data'}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={() => setIsExpanded(!isExpanded)}
            >
              {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={() => copyToClipboard(JSON.stringify(data, null, 2), 'root')}
            >
              <Copy className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </CardHeader>
      {isExpanded && (
        <CardContent className="pt-0">
          <ScrollArea className="h-[300px] w-full">
            <div className="font-mono text-sm">
              {renderValue(data)}
            </div>
          </ScrollArea>
          {copiedPath && (
            <div className="mt-2 text-xs text-green-600 dark:text-green-400">
              ✓ Copied to clipboard
            </div>
          )}
        </CardContent>
      )}
    </Card>
  )
}

export function HITLModal() {
  const { hitlRequest, clearHITLRequest } = useTaskGraphStore()
  const [selectedAction, setSelectedAction] = useState<'approve' | 'modify' | 'abort' | null>(null)
  const [modificationInstructions, setModificationInstructions] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isWaitingForModification, setIsWaitingForModification] = useState(false)
  const [lastProcessedRequestId, setLastProcessedRequestId] = useState<string | null>(null)

  const isOpen = hitlRequest !== null
  const request = hitlRequest as HITLRequest | null

  // Reset state when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setSelectedAction(null)
      setModificationInstructions('')
      setIsSubmitting(false)
    }
  }, [isOpen])

  // CRITICAL: Detect when a new HITL request arrives and reset waiting state
  useEffect(() => {
    if (request && request.request_id !== lastProcessedRequestId) {
      console.log('🔄 New HITL request detected:', {
        newRequestId: request.request_id,
        lastProcessedId: lastProcessedRequestId,
        checkpoint: request.checkpoint_name,
        attempt: request.current_attempt
      })
      
      // Reset all states for the new request
      setIsWaitingForModification(false)
      setSelectedAction(null)
      setModificationInstructions('')
      setIsSubmitting(false)
      setLastProcessedRequestId(request.request_id)
      
      console.log('✅ Reset modal state for new request')
    }
  }, [request?.request_id, lastProcessedRequestId])

  const handleClose = () => {
    if (!isSubmitting && !isWaitingForModification) {
      clearHITLRequest()
      setSelectedAction(null)
      setModificationInstructions('')
      setIsWaitingForModification(false)
      setLastProcessedRequestId(null)
    }
  }

  const handleResponse = async (action: 'approve' | 'modify' | 'abort', feedback?: string) => {
    if (!hitlRequest || isSubmitting) return

    setIsSubmitting(true)
    
    try {
      console.log('📤 Sending HITL response:', {
        action,
        requestId: hitlRequest.request_id,
        feedback: feedback?.substring(0, 100) + (feedback && feedback.length > 100 ? '...' : '')
      })

      await webSocketService.sendHITLResponse({
        request_id: hitlRequest.request_id,
        action,
        modification_instructions: feedback || ''
      })

      if (action === 'modify') {
        console.log('⏳ Waiting for modified plan...')
        setIsWaitingForModification(true)
        setSelectedAction(null)
        setModificationInstructions('')
        // Don't clear the request - wait for the new one
      } else {
        console.log('✅ Action completed, clearing request')
        clearHITLRequest()
        setIsWaitingForModification(false)
        setLastProcessedRequestId(null)
      }
    } catch (error) {
      console.error('Failed to send HITL response:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleActionSelect = (action: 'approve' | 'modify' | 'abort') => {
    setSelectedAction(action)
    
    if (action === 'approve' || action === 'abort') {
      handleResponse(action)
    }
  }

  const handleModifySubmit = () => {
    if (modificationInstructions.trim()) {
      handleResponse('modify', modificationInstructions.trim())
    }
  }

  if (!request) {
    return null
  }

  const getCheckpointIcon = (checkpoint: string) => {
    if (checkpoint.includes('Plan')) return <Brain className="h-5 w-5" />
    if (checkpoint.includes('Execute')) return <Zap className="h-5 w-5" />
    return <Target className="h-5 w-5" />
  }

  const getAttemptBadgeVariant = (attempt: number) => {
    if (attempt === 1) return 'default'
    if (attempt <= 3) return 'secondary'
    return 'destructive'
  }

  // Determine if this is a modified plan (attempt > 1)
  const isModifiedPlan = request.current_attempt > 1

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-6xl w-full max-h-[90vh] p-0 gap-0 overflow-hidden">
        {/* Header */}
        <DialogHeader className="px-6 py-4 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/50 dark:to-indigo-950/50 border-b">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 dark:bg-blue-900/50 rounded-lg">
                {getCheckpointIcon(request.checkpoint_name)}
              </div>
              <div>
                <DialogTitle className="text-xl font-semibold text-foreground">
                  {isModifiedPlan ? 'Review Modified Plan' : 'Human Review Required'}
                </DialogTitle>
                <DialogDescription className="text-sm text-muted-foreground mt-1">
                  {request.checkpoint_name}
                  {isModifiedPlan && ' - Plan has been updated based on your feedback'}
                </DialogDescription>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={getAttemptBadgeVariant(request.current_attempt)}>
                Attempt {request.current_attempt}
              </Badge>
              <Badge variant="outline" className="text-xs">
                {request.node_id}
              </Badge>
            </div>
          </div>
        </DialogHeader>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          <ScrollArea className="h-[calc(90vh-200px)]">
            <div className="p-6 space-y-6">
              {/* Context Message */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <MessageSquare className="h-4 w-4" />
                    Context
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-sm leading-relaxed">{request.context_message}</p>
                  {isModifiedPlan && (
                    <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-200 dark:border-blue-800">
                      <p className="text-sm text-blue-800 dark:text-blue-300">
                        <RefreshCw className="h-4 w-4 inline mr-2" />
                        This plan has been updated based on your previous feedback. Please review the changes.
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Task Goal */}
              {request.data_for_review?.task_goal && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                      <Target className="h-4 w-4" />
                      Task Goal
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <p className="text-sm leading-relaxed font-medium">
                      {request.data_for_review.task_goal}
                    </p>
                  </CardContent>
                </Card>
              )}

              {/* Plan Viewer - Specialized for plans */}
              {request.data_for_review && (
                <PlanViewer planData={request.data_for_review} isModified={isModifiedPlan} />
              )}

              {/* Raw Data Viewer - Collapsible */}
              <JsonViewer data={request.data_for_review} title="Raw Data (Advanced)" />

              {/* Action Selection */}
              {!isWaitingForModification && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium">
                      {isModifiedPlan ? 'Review Modified Plan' : 'Choose Action'}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0 space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <Button
                        variant={selectedAction === 'approve' ? 'default' : 'outline'}
                        className="h-auto p-4 flex flex-col items-center gap-2"
                        onClick={() => handleActionSelect('approve')}
                        disabled={isSubmitting}
                      >
                        <CheckCircle className="h-5 w-5 text-green-600" />
                        <div className="text-center">
                          <div className="font-medium">Approve</div>
                          <div className="text-xs text-muted-foreground">
                            {isModifiedPlan ? 'Accept modified plan' : 'Continue as planned'}
                          </div>
                        </div>
                      </Button>

                      <Button
                        variant={selectedAction === 'modify' ? 'default' : 'outline'}
                        className="h-auto p-4 flex flex-col items-center gap-2"
                        onClick={() => setSelectedAction('modify')}
                        disabled={isSubmitting}
                      >
                        <Edit className="h-5 w-5 text-blue-600" />
                        <div className="text-center">
                          <div className="font-medium">Request Changes</div>
                          <div className="text-xs text-muted-foreground">
                            {isModifiedPlan ? 'Request further changes' : 'Provide feedback'}
                          </div>
                        </div>
                      </Button>

                      <Button
                        variant={selectedAction === 'abort' ? 'destructive' : 'outline'}
                        className="h-auto p-4 flex flex-col items-center gap-2"
                        onClick={() => handleActionSelect('abort')}
                        disabled={isSubmitting}
                      >
                        <XCircle className="h-5 w-5 text-red-600" />
                        <div className="text-center">
                          <div className="font-medium">Abort</div>
                          <div className="text-xs text-muted-foreground">Stop execution</div>
                        </div>
                      </Button>
                    </div>

                    {/* Modification Instructions */}
                    {selectedAction === 'modify' && (
                      <div className="space-y-3 pt-4 border-t">
                        <label className="text-sm font-medium">
                          {isModifiedPlan ? 'Additional Modification Instructions' : 'Modification Instructions'}
                        </label>
                        <Textarea
                          placeholder={isModifiedPlan 
                            ? "Describe what additional changes you'd like to see..."
                            : "Describe what changes you'd like to see..."
                          }
                          value={modificationInstructions}
                          onChange={(e) => setModificationInstructions(e.target.value)}
                          className="min-h-[100px]"
                        />
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="outline"
                            onClick={() => setSelectedAction(null)}
                            disabled={isSubmitting}
                          >
                            Cancel
                          </Button>
                          <Button
                            onClick={handleModifySubmit}
                            disabled={!modificationInstructions.trim() || isSubmitting}
                          >
                            {isSubmitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            Submit Changes
                          </Button>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Waiting for Modification */}
              {isWaitingForModification && (
                <Card>
                  <CardContent className="p-6 text-center">
                    <div className="flex flex-col items-center gap-3">
                      <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
                      <div>
                        <h3 className="font-medium">Processing Your Feedback</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                          The system is incorporating your changes and will present a revised plan shortly.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Request Details */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <Clock className="h-4 w-4" />
                    Request Details
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Request ID:</span>
                      <div className="font-mono text-xs mt-1 p-2 bg-muted rounded">
                        {request.request_id}
                      </div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Timestamp:</span>
                      <div className="mt-1">
                        {new Date(request.timestamp).toLocaleString()}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </ScrollArea>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-muted/30 border-t">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-4">
              <span>Node: {request.node_id}</span>
              <span>•</span>
              <span>Checkpoint: {request.checkpoint_name}</span>
              {isModifiedPlan && (
                <>
                  <span>•</span>
                  <span className="text-blue-600 dark:text-blue-400">Modified Plan</span>
                </>
              )}
            </div>
            <div className="flex items-center gap-2">
              {isSubmitting && (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>Processing...</span>
                </>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
} 