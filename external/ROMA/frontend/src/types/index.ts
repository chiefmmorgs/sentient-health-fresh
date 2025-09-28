export interface TaskNode {
  task_id: string
  goal: string
  task_type: string
  node_type: 'PLAN' | 'EXECUTE'
  agent_name?: string
  layer: number
  parent_node_id?: string
  sub_graph_id?: string
  status: TaskStatus
  output_summary?: string
  full_result?: any
  error?: string
  input_payload_summary?: string
  timestamp_created?: string
  timestamp_updated?: string
  timestamp_completed?: string
  planned_sub_task_ids?: string[]
  input_context_sources?: ContextSource[]
  model_display?: string
  model_info?: ModelInfo
  execution_details?: ExecutionDetails
}

export interface ModelInfo {
  adapter_name?: string
  model_provider?: string
  model_name?: string
  model_id?: string
}

export interface ToolCall {
  // Basic tool execution data
  tool_call_id?: string
  tool_name: string
  tool_args?: Record<string, any>
  result?: string
  created_at?: number
  tool_call_error?: boolean
  
  // Execution context and lifecycle
  requires_confirmation?: boolean
  confirmed?: boolean
  requires_user_input?: boolean
  external_execution_required?: boolean
  stop_after_tool_call?: boolean
  
  // Performance metrics and timing
  execution_duration_ms?: number      // Duration in milliseconds
  tokens_per_second?: number          // Calculated performance metric
  cache_efficiency_percent?: number   // Cache hit percentage
  
  // Result metadata
  result_size_bytes?: number
  result_truncated?: boolean
  result_full_size?: number
  
  // Toolkit identification
  toolkit_name?: string | null  // Only for custom toolkits
  toolkit_category?: string     // search, web, social, data, local, crypto, etc.
  toolkit_type?: string        // custom, agno, unknown
  toolkit_icon?: string        // Icon for display
  
  // Comprehensive metrics from MessageMetrics
  metrics?: {
    // Basic token usage
    input_tokens?: number
    output_tokens?: number
    total_tokens?: number
    cached_tokens?: number
    cache_write_tokens?: number
    reasoning_tokens?: number
    audio_tokens?: number
    input_audio_tokens?: number
    output_audio_tokens?: number
    
    // Token breakdowns
    prompt_tokens?: number
    completion_tokens?: number
    prompt_tokens_details?: Record<string, any>
    completion_tokens_details?: Record<string, any>
    
    // Timing metrics (from LLM execution)
    time_to_first_token?: number  // Time to first token in seconds
    
    // Additional custom metrics
    additional_metrics?: Record<string, any>
  }
}

export interface ExecutionDetails {
  processing_started?: string
  processing_completed?: string
  success?: boolean
  error?: string
  model_info?: ModelInfo
  tool_calls?: ToolCall[]
}

export type TaskStatus = 
  | 'PENDING'
  | 'READY' 
  | 'RUNNING'
  | 'PLAN_DONE'
  | 'AGGREGATING'
  | 'DONE'
  | 'FAILED'
  | 'NEEDS_REPLAN'
  | 'CANCELLED'

export interface ContextSource {
  source_task_id: string
  source_task_goal_summary: string
  content_type: string
  content_type_description?: string
}

export interface TaskGraph {
  edges: GraphEdge[]
}

export interface GraphEdge {
  source: string
  target: string
}

export interface APIResponse {
  overall_project_goal?: string
  all_nodes: Record<string, TaskNode>
  graphs: Record<string, TaskGraph>
}

export interface HITLRequest {
  checkpoint_name: string
  context_message: string
  data_for_review: any
  node_id: string
  current_attempt: number
}

export interface HITLResponse {
  user_choice: 'approved' | 'request_modification' | 'aborted'
  message?: string
  modification_instructions?: string
}

// React Flow types
export interface FlowNode {
  id: string
  type: string
  position: { x: number; y: number }
  data: {
    label: string
    node: TaskNode
    isSelected?: boolean
  }
  style?: any
}

export interface FlowEdge {
  id: string
  source: string
  target: string
  type?: string
  style?: any
  data?: any
} 