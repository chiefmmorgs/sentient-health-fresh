import React, { useState } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  X,
  Clock,
  User,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Calendar,
  FileText
} from 'lucide-react'
import { cn } from '@/lib/utils'
import FullResultModal from './FullResultModal'
import type { TaskNode } from '@/types'

const ComparisonPanel: React.FC = () => {
  const {
    isComparisonPanelOpen,
    comparisonView,
    toggleComparisonPanel,
    getSelectedNodes,
    getSelectionStats
  } = useTaskGraphStore()

  const [fullResultNode, setFullResultNode] = useState<TaskNode | null>(null)
  const selectedNodes = getSelectedNodes()
  const stats = getSelectionStats()

  if (!isComparisonPanelOpen || selectedNodes.length < 2) {
    return null
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'DONE': return <CheckCircle className="w-4 h-4 text-green-600" />
      case 'FAILED': return <XCircle className="w-4 h-4 text-red-600" />
      case 'RUNNING': return <div className="w-4 h-4 border-2 border-orange-600 border-t-transparent rounded-full animate-spin" />
      default: return <AlertTriangle className="w-4 h-4 text-amber-600" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'DONE': return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
      case 'FAILED': return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
      case 'RUNNING': return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300'
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300'
    }
  }

  const formatExecutionTime = (node: TaskNode) => {
    if (!node.timestamp_created || !node.timestamp_completed) return 'N/A'
    const created = new Date(node.timestamp_created).getTime()
    const completed = new Date(node.timestamp_completed).getTime()
    const duration = completed - created
    return `${(duration / 1000).toFixed(1)}s`
  }

  const renderCardsView = () => (
    <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
      {selectedNodes.map((node, index) => (
        <div key={node.task_id} className="border rounded-lg p-4 bg-card">
          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center space-x-2">
              <Badge variant="outline" className="text-xs">
                #{index + 1}
              </Badge>
              <Badge className={cn("text-xs", getStatusColor(node.status))}>
                {node.status}
              </Badge>
            </div>
            {getStatusIcon(node.status)}
          </div>

          {/* Content */}
          <div className="space-y-3">
            <div>
              <h4 className="font-medium text-sm mb-1">{node.task_type}</h4>
              <p className="text-xs text-muted-foreground line-clamp-3">
                {node.goal}
              </p>
            </div>

            {/* Metadata */}
            <div className="space-y-2 text-xs text-muted-foreground">
              <div className="flex items-center space-x-2">
                <User className="w-3 h-3" />
                <span>{node.agent_name || 'Unknown Agent'}</span>
              </div>
              
              <div className="flex items-center space-x-2">
                <Clock className="w-3 h-3" />
                <span>{formatExecutionTime(node)}</span>
              </div>

              <div className="flex items-center space-x-2">
                <BarChart3 className="w-3 h-3" />
                <span>Layer {node.layer}</span>
              </div>
            </div>

            {/* Actions */}
            {(node.full_result || node.output_summary) && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setFullResultNode(node)}
                className="w-full text-xs"
              >
                <FileText className="w-3 h-3 mr-1" />
                View Result
              </Button>
            )}
          </div>
        </div>
      ))}
    </div>
  )

  const renderTableView = () => (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b">
            <th className="text-left p-3 font-medium">#</th>
            <th className="text-left p-3 font-medium">Task Type</th>
            <th className="text-left p-3 font-medium">Goal</th>
            <th className="text-left p-3 font-medium">Status</th>
            <th className="text-left p-3 font-medium">Agent</th>
            <th className="text-left p-3 font-medium">Layer</th>
            <th className="text-left p-3 font-medium">Duration</th>
            <th className="text-left p-3 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {selectedNodes.map((node, index) => (
            <tr key={node.task_id} className="border-b hover:bg-muted/50">
              <td className="p-3">
                <Badge variant="outline" className="text-xs">#{index + 1}</Badge>
              </td>
              <td className="p-3">
                <Badge variant="secondary" className="text-xs">{node.task_type}</Badge>
              </td>
              <td className="p-3 max-w-xs">
                <div className="truncate" title={node.goal}>
                  {node.goal}
                </div>
              </td>
              <td className="p-3">
                <div className="flex items-center space-x-2">
                  {getStatusIcon(node.status)}
                  <Badge className={cn("text-xs", getStatusColor(node.status))}>
                    {node.status}
                  </Badge>
                </div>
              </td>
              <td className="p-3 text-muted-foreground">
                {node.agent_name || 'Unknown'}
              </td>
              <td className="p-3 text-muted-foreground">
                {node.layer}
              </td>
              <td className="p-3 text-muted-foreground">
                {formatExecutionTime(node)}
              </td>
              <td className="p-3">
                {(node.full_result || node.output_summary) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setFullResultNode(node)}
                    className="h-6 px-2 text-xs"
                  >
                    View
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  const renderTimelineView = () => {
    const sortedNodes = selectedNodes
      .filter(node => node.timestamp_created)
      .sort((a, b) => 
        new Date(a.timestamp_created!).getTime() - new Date(b.timestamp_created!).getTime()
      )

    return (
      <div className="space-y-4">
        {sortedNodes.map((node, index) => (
          <div key={node.task_id} className="flex items-start space-x-4">
            {/* Timeline indicator */}
            <div className="flex flex-col items-center">
              <div className={cn(
                "w-3 h-3 rounded-full border-2",
                node.status === 'DONE' ? "bg-green-500 border-green-500" :
                node.status === 'FAILED' ? "bg-red-500 border-red-500" :
                node.status === 'RUNNING' ? "bg-orange-500 border-orange-500" :
                "bg-gray-300 border-gray-300"
              )} />
              {index < sortedNodes.length - 1 && (
                <div className="w-0.5 h-12 bg-border mt-2" />
              )}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center space-x-2 mb-1">
                <Badge variant="outline" className="text-xs">{node.task_type}</Badge>
                <Badge className={cn("text-xs", getStatusColor(node.status))}>
                  {node.status}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {new Date(node.timestamp_created!).toLocaleTimeString()}
                </span>
              </div>
              
              <p className="text-sm mb-2">{node.goal}</p>
              
              <div className="flex items-center space-x-4 text-xs text-muted-foreground">
                <span>👤 {node.agent_name || 'Unknown'}</span>
                <span>📊 Layer {node.layer}</span>
                <span>⏱️ {formatExecutionTime(node)}</span>
              </div>
            </div>

            {/* Actions */}
            <div>
              {(node.full_result || node.output_summary) && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setFullResultNode(node)}
                  className="h-6 px-2 text-xs"
                >
                  View
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
    )
  }

  const renderMetricsView = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {/* Overall Stats */}
      <div className="space-y-4">
        <h4 className="font-medium text-sm">Overview</h4>
        <div className="space-y-3">
          <div className="flex justify-between">
            <span className="text-sm text-muted-foreground">Total Tasks</span>
            <span className="text-sm font-medium">{stats.total}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sm text-muted-foreground">Success Rate</span>
            <span className="text-sm font-medium">{stats.successRate.toFixed(1)}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sm text-muted-foreground">Avg Duration</span>
            <span className="text-sm font-medium">
              {stats.avgExecutionTime ? `${(stats.avgExecutionTime / 1000).toFixed(1)}s` : 'N/A'}
            </span>
          </div>
        </div>
      </div>

      {/* Status Breakdown */}
      <div className="space-y-4">
        <h4 className="font-medium text-sm">Status Distribution</h4>
        <div className="space-y-2">
          {Object.entries(stats.byStatus).map(([status, count]) => (
            <div key={status} className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                {getStatusIcon(status)}
                <span className="text-sm">{status}</span>
              </div>
              <Badge variant="outline" className="text-xs">{count}</Badge>
            </div>
          ))}
        </div>
      </div>

      {/* Task Type Breakdown */}
      <div className="space-y-4">
        <h4 className="font-medium text-sm">Task Types</h4>
        <div className="space-y-2">
          {Object.entries(stats.byTaskType).map(([type, count]) => (
            <div key={type} className="flex justify-between">
              <span className="text-sm text-muted-foreground">{type}</span>
              <Badge variant="secondary" className="text-xs">{count}</Badge>
            </div>
          ))}
        </div>
      </div>

      {/* Layer Distribution */}
      <div className="space-y-4">
        <h4 className="font-medium text-sm">Layer Distribution</h4>
        <div className="space-y-2">
          {Object.entries(stats.byLayer)
            .sort(([a], [b]) => Number(a) - Number(b))
            .map(([layer, count]) => (
            <div key={layer} className="flex justify-between">
              <span className="text-sm text-muted-foreground">Layer {layer}</span>
              <Badge variant="outline" className="text-xs">{count}</Badge>
            </div>
          ))}
        </div>
      </div>
    </div>
  )

  const renderView = () => {
    switch (comparisonView) {
      case 'table': return renderTableView()
      case 'timeline': return renderTimelineView()
      case 'metrics': return renderMetricsView()
      default: return renderCardsView()
    }
  }

  return (
    <>
      <div className="border-l bg-card h-full w-96 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div>
            <h3 className="font-medium">Compare Tasks</h3>
            <p className="text-sm text-muted-foreground">
              {selectedNodes.length} tasks selected
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleComparisonPanel}
            className="h-8 w-8 p-0"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {renderView()}
        </div>
      </div>

      {/* Full Result Modal */}
      {fullResultNode && (
        <FullResultModal
          isOpen={!!fullResultNode}
          onClose={() => setFullResultNode(null)}
          node={fullResultNode}
        />
      )}
    </>
  )
}

export default ComparisonPanel 