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
  FileText,
  Code,
  Database,
  Image,
  Link2,
  Search,
  Eye,
  EyeOff
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { TaskNode } from '@/types'
import AdvancedMarkdownViewer from '@/components/ui/AdvancedMarkdownViewer'

interface FullResultModalProps {
  isOpen: boolean
  onClose: () => void
  node: TaskNode
}

interface FormattedData {
  type: 'markdown' | 'json' | 'text' | 'html' | 'url' | 'image' | 'unknown'
  content: string
  size: string
  isLarge: boolean
  source: string // Which field the content came from
}

const formatDataSize = (str: string): string => {
  const bytes = new Blob([str]).size
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const detectDataType = (node: TaskNode): FormattedData => {
  // Priority order: look for specific fields with complete content first
  const candidates = [
    // Check for the specific field that contains complete search results with citations
    { field: 'full_result.output_text_with_citations', data: node.full_result?.output_text_with_citations, type: 'markdown' as const },
    
    // Check for other potential markdown fields in full_result
    { field: 'full_result.output_text', data: node.full_result?.output_text, type: 'markdown' as const },
    { field: 'full_result.result', data: node.full_result?.result, type: 'unknown' as const },
    
    // Check for common markdown field names at root level
    { field: 'output_summary_markdown', data: (node as any).output_summary_markdown, type: 'markdown' as const },
    { field: 'result_markdown', data: (node as any).result_markdown, type: 'markdown' as const },
    { field: 'markdown_result', data: (node as any).markdown_result, type: 'markdown' as const },
    { field: 'output_markdown', data: (node as any).output_markdown, type: 'markdown' as const },
    
    // Then check full_result as a whole (for non-search nodes)
    { field: 'full_result', data: node.full_result, type: 'unknown' as const },
    
    // Finally fall back to output_summary (truncated version)
    { field: 'output_summary', data: node.output_summary, type: 'text' as const }
  ]

  // Find the first available candidate with substantial content
  for (const candidate of candidates) {
    if (candidate.data && 
        candidate.data !== null && 
        candidate.data !== undefined && 
        String(candidate.data).trim().length > 0) {
      
      let content: string
      let type = candidate.type

      if (typeof candidate.data === 'string') {
        content = candidate.data
      } else {
        content = JSON.stringify(candidate.data, null, 2)
        type = 'json'
      }

      // Skip if this is just a truncated version and we might have better content
      // Check if content looks truncated (ends with "..." or mentions annotations)
      if (candidate.field === 'output_summary' && 
          (content.includes('...') || content.match(/\(\d+\s+annotations?\)/))) {
        // Continue to next candidate to see if we have better content
        continue
      }

      // Auto-detect markdown if not already specified
      if (type === 'unknown' || type === 'text') {
        if (content.includes('# ') || content.includes('## ') || content.includes('**') || content.includes('- ') || content.includes('[') || content.includes('*')) {
          type = 'markdown'
        } else if (content.trim().startsWith('{') || content.trim().startsWith('[')) {
          try {
            JSON.parse(content)
            type = 'json'
          } catch {
            type = 'text'
          }
        } else if (content.includes('<html') || content.includes('<!DOCTYPE')) {
          type = 'html'
        } else if (content.match(/^https?:\/\//)) {
          type = 'url'
        } else if (content.match(/\.(jpg|jpeg|png|gif|svg|webp)$/i)) {
          type = 'image'
        } else {
          type = 'text'
        }
      }

      const size = formatDataSize(content)
      const isLarge = content.length > 10000

      return { type, content, size, isLarge, source: candidate.field }
    }
  }

  // Fallback if no content found
  return { 
    type: 'text', 
    content: 'No result data available', 
    size: '0 B', 
    isLarge: false, 
    source: 'none' 
  }
}

const getTypeIcon = (type: FormattedData['type']) => {
  const iconProps = { className: "w-4 h-4" }
  
  switch (type) {
    case 'markdown':
      return <FileText {...iconProps} />
    case 'json':
      return <Code {...iconProps} />
    case 'html':
      return <FileText {...iconProps} />
    case 'url':
      return <Link2 {...iconProps} />
    case 'image':
      return <Image {...iconProps} />
    case 'text':
      return <FileText {...iconProps} />
    default:
      return <Database {...iconProps} />
  }
}

const getTypeColor = (type: FormattedData['type']) => {
  switch (type) {
    case 'markdown':
      return 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300'
    case 'json':
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
    case 'html':
      return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300'
    case 'url':
      return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
    case 'image':
      return 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300'
    case 'text':
      return 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300'
    default:
      return 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300'
  }
}

const AdvancedMarkdownViewerComponent: React.FC<{ content: string }> = ({ content }) => {
  return (
    <div className="overflow-auto">
      <AdvancedMarkdownViewer 
        content={content}
        maxHeight="none"
        title="Markdown Result"
        showControls={true}
      />
    </div>
  )
}

const JsonViewer: React.FC<{ content: string }> = ({ content }) => {
  const [isCollapsed, setIsCollapsed] = useState(false)

  const highlightJson = (jsonString: string) => {
    return jsonString
      .replace(/("([^"\\]|\\.)*")\s*:/g, '<span class="text-blue-600 dark:text-blue-400 font-medium">$1</span>:')
      .replace(/:\s*("([^"\\]|\\.)*")/g, ': <span class="text-green-600 dark:text-green-400">$1</span>')
      .replace(/:\s*(true|false|null)/g, ': <span class="text-purple-600 dark:text-purple-400 font-medium">$1</span>')
      .replace(/:\s*(\d+)/g, ': <span class="text-orange-600 dark:text-orange-400">$1</span>')
  }

  const displayContent = useMemo(() => {
    if (isCollapsed) {
      try {
        const parsed = JSON.parse(content)
        return JSON.stringify(parsed, null, 0)
      } catch {
        return content.split('\n').slice(0, 5).join('\n') + '\n...'
      }
    }
    return content
  }, [content, isCollapsed])

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">JSON Format</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="h-6 px-2 text-xs"
        >
          {isCollapsed ? (
            <>
              <Eye className="w-3 h-3 mr-1" />
              Expand
            </>
          ) : (
            <>
              <EyeOff className="w-3 h-3 mr-1" />
              Collapse
            </>
          )}
        </Button>
      </div>
      <pre 
        className="text-xs font-mono bg-muted/30 p-4 rounded-lg overflow-auto border"
        dangerouslySetInnerHTML={{ __html: highlightJson(displayContent) }}
      />
    </div>
  )
}

const TextViewer: React.FC<{ content: string; type: FormattedData['type'] }> = ({ content, type }) => {
  const [searchTerm, setSearchTerm] = useState('')
  const [isSearchVisible, setIsSearchVisible] = useState(false)

  const highlightedContent = useMemo(() => {
    if (!searchTerm.trim()) return content

    const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
    return content.replace(regex, '<mark class="bg-yellow-200 dark:bg-yellow-800">$1</mark>')
  }, [content, searchTerm])

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {type.charAt(0).toUpperCase() + type.slice(1)} Content
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsSearchVisible(!isSearchVisible)}
          className="h-6 px-2 text-xs"
        >
          <Search className="w-3 h-3 mr-1" />
          Search
        </Button>
      </div>
      
      {isSearchVisible && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-3 h-3 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search in content..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-8 pr-3 py-2 text-sm border rounded-md bg-background"
          />
        </div>
      )}
      
      <pre 
        className="text-xs font-mono bg-muted/30 p-4 rounded-lg overflow-auto border whitespace-pre-wrap"
        dangerouslySetInnerHTML={{ __html: highlightedContent }}
      />
    </div>
  )
}

const UrlViewer: React.FC<{ content: string }> = ({ content }) => {
  return (
    <div className="space-y-2">
      <span className="text-sm text-muted-foreground">URL Content</span>
      <div className="p-4 bg-muted/30 rounded-lg border">
        <a 
          href={content} 
          target="_blank" 
          rel="noopener noreferrer"
          className="text-blue-600 dark:text-blue-400 hover:underline break-all"
        >
          {content}
        </a>
      </div>
    </div>
  )
}

const FullResultModal: React.FC<FullResultModalProps> = ({ isOpen, onClose, node }) => {
  const [copiedField, setCopiedField] = useState<string | null>(null)

  const formattedData = useMemo(() => {
    return detectDataType(node)
  }, [node])

  const copyToClipboard = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedField(field)
      setTimeout(() => setCopiedField(null), 2000)
    } catch (err) {
      console.error('Failed to copy to clipboard:', err)
    }
  }

  const downloadResult = () => {
    const extension = formattedData.type === 'json' ? 'json' : 
                     formattedData.type === 'markdown' ? 'md' : 'txt'
    const filename = `task-result-${node.task_id}-${new Date().toISOString().split('T')[0]}.${extension}`
    
    const mimeType = formattedData.type === 'json' ? 'application/json' : 
                     formattedData.type === 'markdown' ? 'text/markdown' : 'text/plain'
    
    const blob = new Blob([formattedData.content], { type: mimeType })
    
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const renderContent = () => {
    switch (formattedData.type) {
      case 'markdown':
        return <AdvancedMarkdownViewerComponent content={formattedData.content} />
      case 'json':
        return <JsonViewer content={formattedData.content} />
      case 'url':
        return <UrlViewer content={formattedData.content} />
      default:
        return <TextViewer content={formattedData.content} type={formattedData.type} />
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-6xl max-h-[90vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <DialogTitle className="text-xl">Full Task Result</DialogTitle>
              <Badge className={cn("text-xs", getTypeColor(formattedData.type))}>
                {getTypeIcon(formattedData.type)}
                <span className="ml-1">{formattedData.type.toUpperCase()}</span>
              </Badge>
            </div>
            <div className="text-xs text-muted-foreground">
              {formattedData.size}
            </div>
          </div>
          <DialogDescription className="text-left">
            <div className="space-y-1">
              <div><strong>Task:</strong> {node.goal}</div>
              <div><strong>Task ID:</strong> <code className="text-xs bg-muted px-1 rounded">{node.task_id}</code></div>
              <div><strong>Status:</strong> <Badge variant="outline" className="text-xs">{node.status}</Badge></div>
              <div><strong>Source:</strong> <code className="text-xs bg-muted px-1 rounded">{formattedData.source}</code></div>
            </div>
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto overflow-x-auto min-h-0 p-4">
          {renderContent()}
        </div>

        <DialogFooter className="flex-shrink-0">
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => copyToClipboard(formattedData.content, 'content')}
                className="flex items-center space-x-2"
              >
                {copiedField === 'content' ? (
                  <CheckCircle className="w-4 h-4 text-green-600" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
                <span>Copy</span>
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                onClick={downloadResult}
                className="flex items-center space-x-2"
              >
                <Download className="w-4 h-4" />
                <span>Download</span>
              </Button>
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

export default FullResultModal