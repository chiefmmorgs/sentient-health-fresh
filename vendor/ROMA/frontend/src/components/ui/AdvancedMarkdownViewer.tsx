import React, { useState, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import rehypeRaw from 'rehype-raw'
import { Button } from '@/components/ui/button'
import { 
  Eye, 
  EyeOff, 
  Copy, 
  CheckCircle, 
  Download,
  Search,
  ZoomIn,
  ZoomOut,
  RotateCcw
} from 'lucide-react'
import { cn } from '@/lib/utils'
import 'highlight.js/styles/github-dark.css'

interface AdvancedMarkdownViewerProps {
  content: string
  className?: string
  maxHeight?: string
  showControls?: boolean
  title?: string
}

const AdvancedMarkdownViewer: React.FC<AdvancedMarkdownViewerProps> = ({ 
  content, 
  className = "",
  maxHeight = "max-h-96",
  showControls = true,
  title = "Markdown Content"
}) => {
  const [isRawMode, setIsRawMode] = useState(false)
  const [copied, setCopied] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [isSearchVisible, setIsSearchVisible] = useState(false)
  const [fontSize, setFontSize] = useState(14)

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy to clipboard:', err)
    }
  }

  const downloadMarkdown = () => {
    const blob = new Blob([content], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `markdown-content-${new Date().toISOString().split('T')[0]}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const highlightedContent = useMemo(() => {
    if (!searchTerm.trim() || isRawMode) return content

    const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
    return content.replace(regex, '<mark class="bg-yellow-200 dark:bg-yellow-800 px-1 rounded">$1</mark>')
  }, [content, searchTerm, isRawMode])

  const customComponents = {
    // Enhanced table rendering
    table: ({ children, ...props }: any) => (
      <div className="overflow-x-auto my-4">
        <table className="min-w-full border-collapse border border-border rounded-lg" {...props}>
          {children}
        </table>
      </div>
    ),
    thead: ({ children, ...props }: any) => (
      <thead className="bg-muted/50" {...props}>
        {children}
      </thead>
    ),
    th: ({ children, ...props }: any) => (
      <th className="border border-border px-4 py-2 text-left font-semibold" {...props}>
        {children}
      </th>
    ),
    td: ({ children, ...props }: any) => (
      <td className="border border-border px-4 py-2" {...props}>
        {children}
      </td>
    ),
    // Enhanced code blocks
    code: ({ inline, className, children, ...props }: any) => {
      if (inline) {
        return (
          <code 
            className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono border" 
            {...props}
          >
            {children}
          </code>
        )
      }
      return (
        <code 
          className={cn("block bg-muted p-4 rounded-lg overflow-x-auto text-sm font-mono border", className)} 
          {...props}
        >
          {children}
        </code>
      )
    },
    // Enhanced blockquotes
    blockquote: ({ children, ...props }: any) => (
      <blockquote 
        className="border-l-4 border-blue-500 pl-4 py-2 my-4 bg-blue-50 dark:bg-blue-900/20 italic" 
        {...props}
      >
        {children}
      </blockquote>
    ),
    // Enhanced links
    a: ({ children, href, ...props }: any) => (
      <a 
        href={href}
        className="text-blue-600 dark:text-blue-400 hover:underline font-medium"
        target="_blank"
        rel="noopener noreferrer"
        {...props}
      >
        {children}
      </a>
    ),
    // FIXED: Enhanced lists with proper spacing and alignment
    ul: ({ children, ...props }: any) => (
      <ul className="list-disc list-outside ml-6 space-y-1 my-3" {...props}>
        {children}
      </ul>
    ),
    ol: ({ children, ...props }: any) => (
      <ol className="list-decimal list-outside ml-6 space-y-1 my-3" {...props}>
        {children}
      </ol>
    ),
    li: ({ children, ...props }: any) => (
      <li className="leading-relaxed" {...props}>
        <div className="inline">{children}</div>
      </li>
    ),
    // Enhanced headings
    h1: ({ children, ...props }: any) => (
      <h1 className="text-2xl font-bold mb-4 mt-6 pb-2 border-b border-border" {...props}>
        {children}
      </h1>
    ),
    h2: ({ children, ...props }: any) => (
      <h2 className="text-xl font-semibold mb-3 mt-5 pb-1 border-b border-border/50" {...props}>
        {children}
      </h2>
    ),
    h3: ({ children, ...props }: any) => (
      <h3 className="text-lg font-semibold mb-2 mt-4" {...props}>
        {children}
      </h3>
    ),
    h4: ({ children, ...props }: any) => (
      <h4 className="text-base font-semibold mb-2 mt-3" {...props}>
        {children}
      </h4>
    ),
    // Enhanced paragraphs
    p: ({ children, ...props }: any) => (
      <p className="mb-3 leading-relaxed" {...props}>
        {children}
      </p>
    ),
  }

  return (
    <div className={cn("space-y-3", className)}>
      {showControls && (
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center space-x-2">
            <span className="text-sm text-muted-foreground font-medium">{title}</span>
            <div className="flex items-center space-x-1">
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
          </div>
          
          <div className="flex items-center space-x-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsSearchVisible(!isSearchVisible)}
              className="h-6 px-2 text-xs"
            >
              <Search className="w-3 h-3 mr-1" />
              Search
            </Button>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsRawMode(!isRawMode)}
              className="h-6 px-2 text-xs"
            >
              {isRawMode ? (
                <>
                  <Eye className="w-3 h-3 mr-1" />
                  Rendered
                </>
              ) : (
                <>
                  <EyeOff className="w-3 h-3 mr-1" />
                  Raw
                </>
              )}
            </Button>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={copyToClipboard}
              className="h-6 px-2 text-xs"
            >
              {copied ? (
                <CheckCircle className="w-3 h-3 mr-1 text-green-600" />
              ) : (
                <Copy className="w-3 h-3 mr-1" />
              )}
              Copy
            </Button>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={downloadMarkdown}
              className="h-6 px-2 text-xs"
            >
              <Download className="w-3 h-3 mr-1" />
              Download
            </Button>
          </div>
        </div>
      )}
      
      {isSearchVisible && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-3 h-3 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search in content..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-8 pr-3 py-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      )}
      
      <div 
        className={cn(
          "border rounded-lg overflow-auto bg-background",
          maxHeight
        )}
        style={{ fontSize: `${fontSize}px` }}
      >
        {isRawMode ? (
          <pre className="p-4 font-mono text-sm whitespace-pre-wrap leading-relaxed">
            {searchTerm ? (
              <span dangerouslySetInnerHTML={{ __html: highlightedContent }} />
            ) : (
              content
            )}
          </pre>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none p-4 leading-relaxed">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight, rehypeRaw]}
              components={customComponents}
            >
              {searchTerm ? highlightedContent : content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}

export default AdvancedMarkdownViewer 