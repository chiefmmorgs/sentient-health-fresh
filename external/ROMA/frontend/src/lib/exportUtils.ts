export interface ExportData {
  project: any
  tasks: any[]
  metadata: any
}

export function exportToJSON(data: ExportData): string {
  return JSON.stringify(data, null, 2)
}

export function exportToCSV(tasks: any[]): string {
  if (tasks.length === 0) return ''
  
  const headers = Object.keys(tasks[0])
  const csvContent = [
    headers.join(','),
    ...tasks.map(task => 
      headers.map(header => {
        const value = task[header]
        // Escape commas and quotes in CSV
        if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
          return `"${value.replace(/"/g, '""')}"`
        }
        return value
      }).join(',')
    )
  ].join('\n')
  
  return csvContent
}

export function downloadFile(content: string, filename: string, mimeType: string = 'text/plain') {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  
  URL.revokeObjectURL(url)
}

export function exportProjectAsJSON(data: ExportData) {
  const content = exportToJSON(data)
  const filename = `project-${data.project?.id || 'export'}-${new Date().toISOString().split('T')[0]}.json`
  downloadFile(content, filename, 'application/json')
}

export function exportTasksAsCSV(tasks: any[], projectId?: string) {
  const content = exportToCSV(tasks)
  const filename = `tasks-${projectId || 'export'}-${new Date().toISOString().split('T')[0]}.csv`
  downloadFile(content, filename, 'text/csv')
}

// Graph export functionality
export async function exportGraphAsImage(format: 'png' | 'svg'): Promise<void> {
  try {
    // Find the graph container (adjust selector as needed)
    const graphElement = document.querySelector('[data-testid="task-graph"]') || 
                        document.querySelector('.react-flow') ||
                        document.querySelector('#graph-container') ||
                        document.querySelector('.graph-container')
    
    if (!graphElement) {
      throw new Error('Graph element not found')
    }

    if (format === 'svg') {
      // For SVG, try to find an SVG element
      const svgElement = graphElement.querySelector('svg')
      if (svgElement) {
        const svgData = new XMLSerializer().serializeToString(svgElement)
        const svgBlob = new Blob([svgData], { type: 'image/svg+xml' })
        const url = URL.createObjectURL(svgBlob)
        
        const link = document.createElement('a')
        link.href = url
        link.download = `task-graph-${new Date().toISOString().split('T')[0]}.svg`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
        return
      }
    }

    // For PNG or fallback, use html2canvas
    const html2canvas = await import('html2canvas')
    const canvas = await html2canvas.default(graphElement as HTMLElement, {
      backgroundColor: '#ffffff',
      scale: 2, // Higher quality
      useCORS: true,
      allowTaint: true
    })

    canvas.toBlob((blob) => {
      if (blob) {
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `task-graph-${new Date().toISOString().split('T')[0]}.${format}`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
      }
    }, `image/${format}`)

  } catch (error) {
    console.error('Failed to export graph as image:', error)
    throw error
  }
}

// Node data export functionality
export function exportNodesAsJSON(nodes: Record<string, any>, filename?: string): void {
  const data = {
    nodes: Object.values(nodes),
    exported_at: new Date().toISOString(),
    total_count: Object.keys(nodes).length
  }
  
  const content = JSON.stringify(data, null, 2)
  const defaultFilename = `task-nodes-${new Date().toISOString().split('T')[0]}.json`
  downloadFile(content, filename || defaultFilename, 'application/json')
}

export function exportNodesAsCSV(nodes: Record<string, any>, filename?: string): void {
  const nodeArray = Object.values(nodes)
  if (nodeArray.length === 0) {
    throw new Error('No nodes to export')
  }

  // Flatten node data for CSV
  const flattenedNodes = nodeArray.map(node => ({
    id: node.id,
    name: node.name || node.id,
    status: node.status,
    type: node.type,
    created_at: node.created_at,
    updated_at: node.updated_at,
    description: node.description || '',
    output_summary: node.output_summary || '',
    has_full_result: !!node.full_result,
    parent_id: node.parent_id || '',
    children_count: node.children ? node.children.length : 0
  }))

  const content = exportToCSV(flattenedNodes)
  const defaultFilename = `task-nodes-${new Date().toISOString().split('T')[0]}.csv`
  downloadFile(content, filename || defaultFilename, 'text/csv')
}

// Node results export functionality
export function exportNodeResults(nodes: any[], format: 'individual' | 'combined' = 'individual'): void {
  const nodesWithResults = nodes.filter(node => node.full_result || node.output_summary)
  
  if (nodesWithResults.length === 0) {
    throw new Error('No nodes with results to export')
  }

  if (format === 'combined') {
    // Export all results in one file
    const combinedResults = nodesWithResults.map(node => `
# ${node.name || node.id}

**Status:** ${node.status}
**Type:** ${node.type}
**Created:** ${node.created_at ? new Date(node.created_at).toLocaleString() : 'N/A'}

## Summary
${node.output_summary || 'No summary available'}

## Full Result
${node.full_result || 'No detailed result available'}

---
`).join('\n')

    const filename = `combined-results-${new Date().toISOString().split('T')[0]}.md`
    downloadFile(combinedResults, filename, 'text/markdown')
  } else {
    // Export individual files (simulate by creating a zip-like structure)
    nodesWithResults.forEach(node => {
      const content = `# ${node.name || node.id}

**Status:** ${node.status}
**Type:** ${node.type}
**Created:** ${node.created_at ? new Date(node.created_at).toLocaleString() : 'N/A'}

## Summary
${node.output_summary || 'No summary available'}

## Full Result
${node.full_result || 'No detailed result available'}
`
      const filename = `result-${node.id}-${new Date().toISOString().split('T')[0]}.md`
      downloadFile(content, filename, 'text/markdown')
    })
  }
}

// Project report export functionality - unified function with overloads
export function exportProjectReport(
  nodesOrData: Record<string, any> | ExportData, 
  projectGoalOrUndefined?: string, 
  format: 'markdown' | 'html' = 'markdown'
): void {
  // Handle both old and new function signatures
  if ('project' in nodesOrData && 'tasks' in nodesOrData) {
    // Old signature: exportProjectReport(data: ExportData)
    const data = nodesOrData as ExportData
    const report = generateLegacyProjectReport(data)
    const filename = `report-${data.project?.id || 'export'}-${new Date().toISOString().split('T')[0]}.md`
    downloadFile(report, filename, 'text/markdown')
  } else {
    // New signature: exportProjectReport(nodes, projectGoal?, format?)
    const nodes = nodesOrData as Record<string, any>
    const nodeArray = Object.values(nodes)
    const completedNodes = nodeArray.filter(node => node.status === 'completed')
    const totalNodes = nodeArray.length
    const successRate = totalNodes > 0 ? (completedNodes.length / totalNodes * 100).toFixed(1) : '0'

    if (format === 'html') {
      const htmlContent = generateHTMLReport(nodeArray, projectGoalOrUndefined, successRate)
      const filename = `project-report-${new Date().toISOString().split('T')[0]}.html`
      downloadFile(htmlContent, filename, 'text/html')
    } else {
      const markdownContent = generateMarkdownReport(nodeArray, projectGoalOrUndefined, successRate)
      const filename = `project-report-${new Date().toISOString().split('T')[0]}.md`
      downloadFile(markdownContent, filename, 'text/markdown')
    }
  }
}

// Helper functions for report generation
function generateLegacyProjectReport(data: ExportData): string {
  const { project, tasks, metadata } = data
  
  const completedTasks = tasks.filter(task => task.status === 'completed').length
  const totalTasks = tasks.length
  const successRate = totalTasks > 0 ? (completedTasks / totalTasks * 100).toFixed(1) : '0'
  
  return `# Project Report: ${project?.name || 'Untitled Project'}

## Summary
- **Project ID**: ${project?.id || 'N/A'}
- **Created**: ${project?.created_at ? new Date(project.created_at).toLocaleString() : 'N/A'}
- **Status**: ${project?.status || 'N/A'}
- **Total Tasks**: ${totalTasks}
- **Completed Tasks**: ${completedTasks}
- **Success Rate**: ${successRate}%

## Task Breakdown
${tasks.map(task => `
### ${task.name || task.id}
- **Status**: ${task.status}
- **Type**: ${task.type}
- **Created**: ${task.created_at ? new Date(task.created_at).toLocaleString() : 'N/A'}
${task.description ? `- **Description**: ${task.description}` : ''}
${task.result ? `- **Result**: ${task.result}` : ''}
`).join('\n')}

## Metadata
\`\`\`json
${JSON.stringify(metadata, null, 2)}
\`\`\`

---
*Report generated on ${new Date().toLocaleString()}*
`
}

function generateMarkdownReport(nodes: any[], projectGoal?: string, successRate?: string): string {
  return `# Project Report

${projectGoal ? `## Project Goal\n${projectGoal}\n` : ''}

## Summary
- **Total Tasks**: ${nodes.length}
- **Completed Tasks**: ${nodes.filter(n => n.status === 'completed').length}
- **Success Rate**: ${successRate}%
- **Generated**: ${new Date().toLocaleString()}

## Task Breakdown
${nodes.map(node => `
### ${node.name || node.id}
- **Status**: ${node.status}
- **Type**: ${node.type}
- **Created**: ${node.created_at ? new Date(node.created_at).toLocaleString() : 'N/A'}
${node.description ? `- **Description**: ${node.description}` : ''}
${node.output_summary ? `- **Summary**: ${node.output_summary}` : ''}
`).join('\n')}

---
*Report generated on ${new Date().toLocaleString()}*
`
}

function generateHTMLReport(nodes: any[], projectGoal?: string, successRate?: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Report</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .summary { background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .task { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }
        .status { padding: 2px 8px; border-radius: 3px; font-size: 12px; }
        .completed { background: #d4edda; color: #155724; }
        .pending { background: #fff3cd; color: #856404; }
        .failed { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <h1>Project Report</h1>
    
    ${projectGoal ? `<h2>Project Goal</h2><p>${projectGoal}</p>` : ''}
    
    <div class="summary">
        <h2>Summary</h2>
        <ul>
            <li><strong>Total Tasks:</strong> ${nodes.length}</li>
            <li><strong>Completed Tasks:</strong> ${nodes.filter(n => n.status === 'completed').length}</li>
            <li><strong>Success Rate:</strong> ${successRate}%</li>
            <li><strong>Generated:</strong> ${new Date().toLocaleString()}</li>
        </ul>
    </div>
    
    <h2>Task Breakdown</h2>
    ${nodes.map(node => `
        <div class="task">
            <h3>${node.name || node.id}</h3>
            <p><span class="status ${node.status}">${node.status}</span> | Type: ${node.type}</p>
            ${node.description ? `<p><strong>Description:</strong> ${node.description}</p>` : ''}
            ${node.output_summary ? `<p><strong>Summary:</strong> ${node.output_summary}</p>` : ''}
            <small>Created: ${node.created_at ? new Date(node.created_at).toLocaleString() : 'N/A'}</small>
        </div>
    `).join('')}
    
    <footer style="margin-top: 40px; text-align: center; color: #666;">
        <small>Report generated on ${new Date().toLocaleString()}</small>
    </footer>
</body>
</html>`
} 