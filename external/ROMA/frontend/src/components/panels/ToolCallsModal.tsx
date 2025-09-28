import React from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { 
  Cpu,
  Clock,
  Hash,
  CheckCircle,
  AlertTriangle
} from 'lucide-react'
import { TaskNode, ToolCall } from '@/types'
import ToolCallsDisplay from './ToolCallsDisplay'

interface ToolCallsModalProps {
  isOpen: boolean
  onClose: () => void
  node: TaskNode | null
  toolCalls: ToolCall[]
}

export const ToolCallsModal: React.FC<ToolCallsModalProps> = ({
  isOpen,
  onClose,
  node,
  toolCalls
}) => {
  if (!node) return null

  const successfulCalls = toolCalls.filter(call => !call.tool_call_error).length
  const failedCalls = toolCalls.filter(call => call.tool_call_error).length

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Cpu className="w-5 h-5 text-orange-600" />
              <DialogTitle className="text-lg">
                Tool Calls - {node.goal}
              </DialogTitle>
            </div>
            <div className="flex items-center space-x-2">
              <Badge variant="outline" className="text-xs">
                <Hash className="w-3 h-3 mr-1" />
                {node.task_id}
              </Badge>
              <Badge variant={node.status === 'DONE' ? 'default' : 'secondary'} className="text-xs">
                {node.status}
              </Badge>
            </div>
          </div>
          
          <DialogDescription asChild>
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">
                Detailed view of all tool executions for this node
              </p>
              
              {/* Summary Stats */}
              <div className="flex items-center space-x-4 text-xs">
                <div className="flex items-center space-x-1">
                  <CheckCircle className="w-3 h-3 text-green-600" />
                  <span>{successfulCalls} successful</span>
                </div>
                {failedCalls > 0 && (
                  <div className="flex items-center space-x-1">
                    <AlertTriangle className="w-3 h-3 text-red-600" />
                    <span>{failedCalls} failed</span>
                  </div>
                )}
                <div className="flex items-center space-x-1">
                  <Clock className="w-3 h-3 text-muted-foreground" />
                  <span>Total: {toolCalls.length} calls</span>
                </div>
                {node.agent_name && (
                  <Badge variant="outline" className="text-xs">
                    Agent: {node.agent_name}
                  </Badge>
                )}
              </div>
            </div>
          </DialogDescription>
        </DialogHeader>
        
        {/* Tool Calls Content */}
        <div className="flex-1 overflow-y-auto pr-2">
          {toolCalls.length > 0 ? (
            <ToolCallsDisplay toolCalls={toolCalls} />
          ) : (
            <div className="flex items-center justify-center h-32 text-center">
              <div className="space-y-2">
                <Cpu className="w-8 h-8 mx-auto text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  No tool calls found for this node
                </p>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default ToolCallsModal