import React, { useMemo } from 'react'

// ENHANCED: Button visibility with aggressive debugging
const shouldShowViewButton = useMemo(() => {
  const hasFullResult = !!(node.full_result || node.aux_data?.full_result)
  const hasExecutionDetails = !!(node.execution_details || node.aux_data?.execution_details)
  const hasOutputSummary = !!node.output_summary
  const isCompleted = node.status === 'DONE'
  
  const shouldShow = isCompleted && (hasFullResult || hasExecutionDetails || hasOutputSummary)
  
  // AGGRESSIVE DEBUGGING for root nodes
  if (node.layer === 0 && !node.parent_node_id) {
    console.log('🚨 ROOT NODE BUTTON DEBUG:', {
      task_id: node.task_id,
      status: node.status,
      isCompleted,
      hasFullResult,
      hasExecutionDetails,
      hasOutputSummary,
      shouldShow,
      full_result_preview: (node.full_result || node.aux_data?.full_result)?.substring(0, 100)
    })
  }
  
  return shouldShow
}, [node.full_result, node.aux_data?.full_result, node.execution_details, node.aux_data?.execution_details, node.output_summary, node.status, node.layer, node.parent_node_id, node.task_id]) 