import React from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'

const HITLLog: React.FC = () => {
  const { hitlLogs } = useTaskGraphStore()

  if (!hitlLogs || hitlLogs.length === 0) {
    return null
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          🤔 HITL Checkpoints
          <Badge variant="secondary" className="text-xs">
            {hitlLogs.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <ScrollArea className="h-32">
          <div className="space-y-2">
            {hitlLogs.slice(-5).map((log, index) => (
              <div key={index} className="text-xs border-l-2 border-blue-200 pl-2 py-1">
                <div className="font-medium text-blue-700">
                  {log.checkpoint_name}
                </div>
                <div className="text-gray-600 truncate">
                  Node: {log.node_id} | Attempt: {log.current_attempt}
                </div>
                <div className="text-gray-500">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

export default HITLLog 