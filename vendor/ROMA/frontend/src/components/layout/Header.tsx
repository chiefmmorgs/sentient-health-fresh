import React from 'react'
import { Button } from '@/components/ui/button'
import { 
  Brain, 
  Download,
  Eye,
  EyeOff
} from 'lucide-react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import ThemeToggle from '@/components/theme/ThemeToggle'
import FilterPanel from '@/components/panels/FilterPanel'
import ExportPanel from '@/components/panels/ExportPanel'
import ContextFlowPanel from '@/components/panels/ContextFlowPanel'
import { exportProjectReport } from '@/lib/exportUtils'

const Header: React.FC = () => {
  const { 
    showContextFlow, 
    toggleContextFlow,
    nodes,
    overallProjectGoal
  } = useTaskGraphStore()

  const hasNodes = Object.keys(nodes).length > 0

  const handleDownloadReport = async () => {
    try {
      // Use the existing export functionality to download as markdown
      exportProjectReport(nodes, overallProjectGoal, 'markdown')
    } catch (error) {
      console.error('Failed to download report:', error)
    }
  }

  return (
    <header className="border-b bg-background/95 backdrop-blur-md supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50 shadow-sm">
      <div className="flex items-center justify-between px-6 py-3">
        {/* Logo and Title */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary">
            <Brain className="w-5 h-5 text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-lg font-semibold">Sentient Research Agent</h1>
            <p className="text-xs text-muted-foreground">
              Hierarchical Task Decomposition System
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center space-x-2">
          {hasNodes && (
            <>
              {/* Filter Panel */}
              <FilterPanel />

              {/* Export Panel */}
              <ExportPanel />

              {/* Context Flow Panel */}
              <ContextFlowPanel />

              {/* Context Flow Toggle */}
              <Button
                variant="outline"
                size="sm"
                onClick={toggleContextFlow}
                className="text-xs"
              >
                {showContextFlow ? (
                  <>
                    <EyeOff className="w-4 h-4 mr-1" />
                    Hide Context Flow
                  </>
                ) : (
                  <>
                    <Eye className="w-4 h-4 mr-1" />
                    Show Context Flow
                  </>
                )}
              </Button>

              {/* Download Report */}
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadReport}
                className="text-xs"
              >
                <Download className="w-4 h-4 mr-1" />
                Download Report
              </Button>
            </>
          )}

          {/* Theme Toggle */}
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}

export default Header 