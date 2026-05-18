export interface Thread {
  id: string
  title: string
  created_at: string
  updated_at: string
  user_renamed?: boolean
}

export interface Source {
  content: string
  similarity: number
  document_name: string
  document_title: string | null
  document_summary: string | null
  document_topics: string[]
  rerank_score?: number
}

export interface WebResult {
  title: string
  url: string
  content: string
  score: number
}

export interface SqlRow {
  id: string
  name: string
  title: string | null
  summary: string | null
  topics: string[] | null
  language: string | null
  status: string
  chunk_count: number | null
  created_at: string
}

export interface SubAgentToolCall {
  name: string
  query?: string
  filters?: Record<string, unknown>
  sources?: Source[]
  web_results?: WebResult[]
  rows?: SqlRow[]
}

export interface SubAgent {
  id: string
  task: string
  reasoning: string
  toolCalls: SubAgentToolCall[]
  summary: string
  isDone: boolean
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  isStreaming?: boolean
  sources?: Source[]
  web_results?: WebResult[]
  sql_rows?: SqlRow[]
  subAgents?: SubAgent[]
}

export interface Document {
  id: string
  name: string
  status: 'pending' | 'processing' | 'done' | 'error'
  chunk_count: number | null
  error_message: string | null
  created_at: string
  title: string | null
  summary: string | null
  topics: string[] | null
  language: string | null
}
