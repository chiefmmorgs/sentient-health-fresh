export interface HITLResponse {
  request_id: string
  checkpoint_name: string
  node_id: string
  action: 'approve' | 'modify' | 'abort'
  modification_instructions?: string | null
  timestamp: string
} 