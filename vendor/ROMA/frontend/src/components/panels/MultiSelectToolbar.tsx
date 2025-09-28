import React from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  CheckSquare,
  Square,
  X,
  RotateCcw,
  BarChart3,
  Download,
  GitCompare,
  Table,
  Calendar,
  Grid3X3
} from 'lucide-react'

const MultiSelectToolbar: React.FC = () => {
  const {
    selectedNodeIds,
    isMultiSelectMode,
    comparisonView,
    isComparisonPanelOpen,
    selectAllNodes,
    clearSelection,
    invertSelection,
    setComparisonView,
    toggleComparisonPanel,
    getFilteredNodes,
    getSelectionStats
  } = useTaskGraphStore()

  const filteredNodes = getFilteredNodes()
  const totalFilteredNodes = Object.keys(filteredNodes).length
  const selectedCount = selectedNodeIds.size
  const stats = getSelectionStats()

  if (!isMultiSelectMode && selectedCount <= 1) {
    return null
  }

  const allSelected = selectedCount === totalFilteredNodes && totalFilteredNodes > 0

  return (
    <div className="border-b bg-muted/30 px-6 py-3">
      <div className="flex items-center justify-between">
        {/* Selection Info */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <Badge variant="secondary" className="text-sm">
              {selectedCount} selected
            </Badge>
            {totalFilteredNodes > selectedCount && (
              <span className="text-sm text-muted-foreground">
                of {totalFilteredNodes} shown
              </span>
            )}
          </div>

          {/* Quick Stats */}
          {selectedCount > 0 && (
            <div className="flex items-center space-x-3 text-sm text-muted-foreground">
              <span>✅ {stats.byStatus.DONE || 0} done</span>
              <span>❌ {stats.byStatus.FAILED || 0} failed</span>
              <span>🔄 {stats.byStatus.RUNNING || 0} running</span>
              <span>📈 {stats.successRate.toFixed(0)}% success</span>
            </div>
          )}
        </div>

        {/* Selection Actions */}
        <div className="flex items-center space-x-2">
          {/* Selection Controls */}
          <div className="flex items-center space-x-1 border rounded-md p-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={selectAllNodes}
              disabled={allSelected}
              className="h-8 px-2"
              title="Select all visible nodes"
            >
              <CheckSquare className="w-4 h-4" />
            </Button>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={invertSelection}
              disabled={totalFilteredNodes === 0}
              className="h-8 px-2"
              title="Invert selection"
            >
              <RotateCcw className="w-4 h-4" />
            </Button>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={clearSelection}
              disabled={selectedCount === 0}
              className="h-8 px-2"
              title="Clear selection"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>

          {/* Comparison View Selector */}
          {selectedCount > 1 && (
            <div className="flex items-center space-x-1 border rounded-md p-1">
              <Button
                variant={comparisonView === 'cards' ? "default" : "ghost"}
                size="sm"
                onClick={() => setComparisonView('cards')}
                className="h-8 px-2"
                title="Card view"
              >
                <Grid3X3 className="w-4 h-4" />
              </Button>
              
              <Button
                variant={comparisonView === 'table' ? "default" : "ghost"}
                size="sm"
                onClick={() => setComparisonView('table')}
                className="h-8 px-2"
                title="Table view"
              >
                <Table className="w-4 h-4" />
              </Button>
              
              <Button
                variant={comparisonView === 'timeline' ? "default" : "ghost"}
                size="sm"
                onClick={() => setComparisonView('timeline')}
                className="h-8 px-2"
                title="Timeline view"
              >
                <Calendar className="w-4 h-4" />
              </Button>
              
              <Button
                variant={comparisonView === 'metrics' ? "default" : "ghost"}
                size="sm"
                onClick={() => setComparisonView('metrics')}
                className="h-8 px-2"
                title="Metrics view"
              >
                <BarChart3 className="w-4 h-4" />
              </Button>
            </div>
          )}

          {/* Comparison Panel Toggle */}
          {selectedCount > 1 && (
            <Button
              variant={isComparisonPanelOpen ? "default" : "outline"}
              size="sm"
              onClick={toggleComparisonPanel}
              className="text-xs"
            >
              <GitCompare className="w-4 h-4 mr-1" />
              Compare
            </Button>
          )}

          {/* Bulk Export */}
          {selectedCount > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                // This would integrate with the existing export functionality
                console.log('Bulk export selected nodes:', selectedCount)
              }}
              className="text-xs"
            >
              <Download className="w-4 h-4 mr-1" />
              Export ({selectedCount})
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

export default MultiSelectToolbar 