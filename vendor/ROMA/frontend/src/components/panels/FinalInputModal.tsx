import React, { useState, useMemo } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Download,
  Copy,
  CheckCircle,
  Search,
  Eye,
  EyeOff,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  MessageSquare,
  Settings,
  User
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { TaskNode } from '@/types'

interface FinalInputModalProps {
  isOpen: boolean
  onClose: () => void
  node: TaskNode
}

type ViewMode = 'both' | 'system' | 'user'

const FinalInputModal: React.FC<FinalInputModalProps> = ({ isOpen, onClose, node }) => {
  const [copied, setCopied] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [isSearchVisible, setIsSearchVisible] = useState(false)
  const [fontSize, setFontSize] = useState(14)
  const [wrapText, setWrapText] = useState(true)
  const [viewMode, setViewMode] = useState<ViewMode>('both')

  // Get the prompts from execution details
  const systemPrompt = useMemo(() => {
    return node.execution_details?.system_prompt || 
           (node as any).aux_data?.execution_details?.system_prompt || 
           'No system prompt available'
  }, [node])

  const userPrompt = useMemo(() => {
    return node.execution_details?.final_llm_input || 
           (node as any).aux_data?.execution_details?.final_llm_input || 
           'No user input available'
  }, [node])

  const hasSystemPrompt = systemPrompt !== 'No system prompt available'
  const hasUserPrompt = userPrompt !== 'No user input available'

  const copyToClipboard = async (content: string, type: string) => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(type)
      setTimeout(() => setCopied(null), 2000)
    } catch (err) {
      console.error('Failed to copy to clipboard:', err)
    }
  }

  const downloadPrompts = () => {
    const content = `SYSTEM PROMPT:\n${systemPrompt}\n\n${'='.repeat(80)}\n\nUSER INPUT:\n${userPrompt}`
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `llm-prompts-${node.task_id}-${new Date().toISOString().split('T')[0]}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const highlightContent = (content: string) => {
    if (!searchTerm.trim()) return content
    const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
    return content.replace(regex, '<mark class="bg-yellow-200 dark:bg-yellow-800 px-1 rounded">$1</mark>')
  }

  const formatDataSize = (str: string): string => {
    const bytes = new Blob([str]).size
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const getSearchMatches = (content: string) => {
    if (!searchTerm.trim()) return 0
    return (content.match(new RegExp(searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')) || []).length
  }

  const totalMatches = getSearchMatches(systemPrompt) + getSearchMatches(userPrompt)

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-7xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <DialogTitle className="text-xl flex items-center space-x-2">
                <MessageSquare className="w-5 h-5 text-indigo-600" />
                <span>LLM Prompts</span>
              </DialogTitle>
              <Badge className="text-xs bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300">
                SYSTEM + USER
              </Badge>
            </div>
            <div className="text-xs text-muted-foreground">
              Total: {formatDataSize(systemPrompt + userPrompt)}
            </div>
          </div>
          <DialogDescription className="text-left">
            <div className="space-y-1">
              <div><strong>Task:</strong> {node.goal}</div>
              <div><strong>Task ID:</strong> <code className="text-xs bg-muted px-1 rounded">{node.task_id}</code></div>
              <div><strong>Agent:</strong> {node.agent_name || 'Unknown'}</div>
              <div><strong>Model:</strong> {node.model_display || node.model_info?.model_name || 'Unknown'}</div>
            </div>
          </DialogDescription>
        </DialogHeader>

        {/* Controls */}
        <div className="flex items-center justify-between flex-wrap gap-2 border-b pb-3">
          <div className="flex items-center space-x-2">
            <span className="text-sm text-muted-foreground font-medium">View:</span>
            
            {/* View Mode Toggle */}
            <div className="flex items-center border rounded-md">
              <Button
                variant={viewMode === 'both' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('both')}
                className="h-7 px-2 text-xs rounded-r-none"
              >
                Both
              </Button>
              <Button
                variant={viewMode === 'system' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('system')}
                className="h-7 px-2 text-xs rounded-none border-x"
                disabled={!hasSystemPrompt}
              >
                <Settings className="w-3 h-3 mr-1" />
                System
              </Button>
              <Button
                variant={viewMode === 'user' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('user')}
                className="h-7 px-2 text-xs rounded-l-none"
                disabled={!hasUserPrompt}
              >
                <User className="w-3 h-3 mr-1" />
                User
              </Button>
            </div>

            {/* Font Size Controls */}
            <div className="flex items-center space-x-1 border rounded-md px-2 py-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setFontSize(Math.max(10, fontSize - 2))}
                className="h-6 w-6 p-0"
                title="Decrease font size"
              >
                <ZoomOut className="w-3 h-3" />
              </Button>
              <span className="text-xs text-muted-foreground min-w-[2rem] text-center">
                {fontSize}px
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setFontSize(Math.min(24, fontSize + 2))}
                className="h-6 w-6 p-0"
                title="Increase font size"
              >
                <ZoomIn className="w-3 h-3" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setFontSize(14)}
                className="h-6 w-6 p-0"
                title="Reset font size"
              >
                <RotateCcw className="w-3 h-3" />
              </Button>
            </div>

            {/* Text Wrap Toggle */}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setWrapText(!wrapText)}
              className="h-7 px-2 text-xs"
              title={wrapText ? "Disable text wrapping" : "Enable text wrapping"}
            >
              {wrapText ? (
                <>
                  <EyeOff className="w-3 h-3 mr-1" />
                  No Wrap
                </>
              ) : (
                <>
                  <Eye className="w-3 h-3 mr-1" />
                  Wrap
                </>
              )}
            </Button>
          </div>
          
          <div className="flex items-center space-x-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsSearchVisible(!isSearchVisible)}
              className="h-7 px-2 text-xs"
            >
              <Search className="w-3 h-3 mr-1" />
              Search
            </Button>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={downloadPrompts}
              className="h-7 px-2 text-xs"
            >
              <Download className="w-3 h-3 mr-1" />
              Download All
            </Button>
          </div>
        </div>

        {/* Search Bar */}
        {isSearchVisible && (
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-3 h-3 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search in prompt content..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-8 pr-3 py-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            {searchTerm && (
              <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-xs text-muted-foreground">
                {totalMatches} matches
              </div>
            )}
          </div>
        )}

        {/* Content Area */}
        <div className="flex-1 overflow-hidden">
          <div className="h-full space-y-4 overflow-auto">
            {/* System Prompt Section */}
            {(viewMode === 'both' || viewMode === 'system') && hasSystemPrompt && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Settings className="w-4 h-4 text-amber-600" />
                    <h3 className="text-sm font-semibold">System Prompt</h3>
                    <Badge variant="outline" className="text-xs">
                      {formatDataSize(systemPrompt)}
                    </Badge>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(systemPrompt, 'system')}
                    className="h-6 px-2 text-xs"
                  >
                    {copied === 'system' ? (
                      <CheckCircle className="w-3 h-3 mr-1 text-green-600" />
                    ) : (
                      <Copy className="w-3 h-3 mr-1" />
                    )}
                    Copy System
                  </Button>
                </div>
                <div 
                  className="border rounded-lg bg-amber-50/50 dark:bg-amber-900/10 max-h-64 overflow-auto"
                  style={{ fontSize: `${fontSize}px` }}
                >
                  <pre 
                    className={cn(
                      "p-4 font-mono leading-relaxed text-foreground",
                      wrapText ? "whitespace-pre-wrap" : "whitespace-pre"
                    )}
                  >
                    {searchTerm ? (
                      <span dangerouslySetInnerHTML={{ __html: highlightContent(systemPrompt) }} />
                    ) : (
                      systemPrompt
                    )}
                  </pre>
                </div>
              </div>
            )}

            {/* User Input Section */}
            {(viewMode === 'both' || viewMode === 'user') && hasUserPrompt && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <User className="w-4 h-4 text-blue-600" />
                    <h3 className="text-sm font-semibold">User Input</h3>
                    <Badge variant="outline" className="text-xs">
                      {formatDataSize(userPrompt)}
                    </Badge>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(userPrompt, 'user')}
                    className="h-6 px-2 text-xs"
                  >
                    {copied === 'user' ? (
                      <CheckCircle className="w-3 h-3 mr-1 text-green-600" />
                    ) : (
                      <Copy className="w-3 h-3 mr-1" />
                    )}
                    Copy User
                  </Button>
                </div>
                <div 
                  className={cn(
                    "border rounded-lg bg-blue-50/50 dark:bg-blue-900/10 overflow-auto",
                    viewMode === 'both' ? "max-h-64" : "max-h-96"
                  )}
                  style={{ fontSize: `${fontSize}px` }}
                >
                  <pre 
                    className={cn(
                      "p-4 font-mono leading-relaxed text-foreground",
                      wrapText ? "whitespace-pre-wrap" : "whitespace-pre"
                    )}
                  >
                    {searchTerm ? (
                      <span dangerouslySetInnerHTML={{ __html: highlightContent(userPrompt) }} />
                    ) : (
                      userPrompt
                    )}
                  </pre>
                </div>
              </div>
            )}

            {/* No Content Message */}
            {!hasSystemPrompt && !hasUserPrompt && (
              <div className="flex items-center justify-center h-32 text-muted-foreground">
                <div className="text-center">
                  <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>No prompt data available for this node</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer with Stats */}
        <DialogFooter className="flex-shrink-0">
          <div className="flex items-center justify-between w-full">
            <div className="text-xs text-muted-foreground space-x-4">
              {hasSystemPrompt && (
                <span>System: {systemPrompt.split('\n').length} lines, {systemPrompt.length.toLocaleString()} chars</span>
              )}
              {hasUserPrompt && (
                <span>User: {userPrompt.split('\n').length} lines, {userPrompt.length.toLocaleString()} chars</span>
              )}
            </div>

            <Button onClick={onClose}>
              Close
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default FinalInputModal 