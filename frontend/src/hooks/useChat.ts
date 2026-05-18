import { useState, useEffect, useCallback, useRef } from 'react'
import type { Session } from '@supabase/supabase-js'
import type { Message, SubAgent, SubAgentToolCall, Source, WebResult, SqlRow } from '@/types'

const API = import.meta.env.VITE_API_BASE_URL as string

export function useChat(
  threadId: string | null,
  session: Session | null,
  onTitleChange?: (threadId: string, title: string) => void,
) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const onTitleChangeRef = useRef(onTitleChange)

  // Keep ref current without adding it to sendMessage's dependency array
  useEffect(() => { onTitleChangeRef.current = onTitleChange })

  useEffect(() => {
    if (!threadId || !session) {
      setMessages([])
      return
    }
    fetch(`${API}/threads/${threadId}/messages`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
      .then(r => r.json())
      .then(setMessages)
      .catch(() => setMessages([]))
  }, [threadId, session])

  const sendMessage = useCallback(async (content: string) => {
    if (!threadId || !session || isStreaming) return

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])

    const assistantId = crypto.randomUUID()
    setMessages(prev => [
      ...prev,
      { id: assistantId, role: 'assistant', content: '', created_at: new Date().toISOString(), isStreaming: true },
    ])
    setIsStreaming(true)

    const currentThreadId = threadId

    try {
      const res = await fetch(`${API}/chat/stream`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ thread_id: currentThreadId, content }),
      })

      if (!res.body) throw new Error('No response body')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'delta') {
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId ? { ...m, content: m.content + event.content } : m
                )
              )
            } else if (event.type === 'tool_result') {
              setMessages(prev =>
                prev.map(m => {
                  if (m.id !== assistantId) return m
                  if (event.tool === 'search_documents') {
                    return { ...m, sources: [...(m.sources ?? []), ...(event.sources ?? [])] }
                  }
                  if (event.tool === 'search_web') {
                    return { ...m, web_results: [...(m.web_results ?? []), ...(event.web_results ?? [])] }
                  }
                  if (event.tool === 'query_documents_metadata') {
                    return { ...m, sql_rows: [...(m.sql_rows ?? []), ...(event.rows ?? [])] }
                  }
                  // Fallback for legacy events without `tool` discriminator
                  if (event.sources) return { ...m, sources: event.sources }
                  return m
                })
              )
            } else if (event.type === 'subagent_start') {
              if (!event.id) continue
              setMessages(prev =>
                prev.map(m => {
                  if (m.id !== assistantId) return m
                  const agent: SubAgent = {
                    id: event.id as string,
                    task: event.task as string,
                    reasoning: '',
                    toolCalls: [],
                    summary: '',
                    isDone: false,
                  }
                  return { ...m, subAgents: [...(m.subAgents ?? []), agent] }
                })
              )
            } else if (event.type === 'subagent_delta') {
              setMessages(prev =>
                prev.map(m => {
                  if (m.id !== assistantId) return m
                  return {
                    ...m,
                    subAgents: (m.subAgents ?? []).map(sa =>
                      sa.id === event.id
                        ? { ...sa, reasoning: (sa.reasoning ?? '') + (event.content as string) }
                        : sa
                    ),
                  }
                })
              )
            } else if (event.type === 'subagent_tool_call') {
              setMessages(prev =>
                prev.map(m => {
                  if (m.id !== assistantId) return m
                  const newCall: SubAgentToolCall = {
                    name: event.name as string,
                    query: event.query as string | undefined,
                    filters: event.filters as Record<string, unknown> | undefined,
                  }
                  return {
                    ...m,
                    subAgents: (m.subAgents ?? []).map(sa =>
                      sa.id === event.id
                        ? { ...sa, toolCalls: [...sa.toolCalls, newCall] }
                        : sa
                    ),
                  }
                })
              )
            } else if (event.type === 'subagent_tool_result') {
              setMessages(prev =>
                prev.map(m => {
                  if (m.id !== assistantId) return m
                  return {
                    ...m,
                    subAgents: (m.subAgents ?? []).map(sa => {
                      if (sa.id !== event.id) return sa
                      const calls = [...sa.toolCalls]
                      // Assumes backend emits tool_call before tool_result sequentially.
                      const lastIdx = calls.length - 1
                      if (lastIdx >= 0) {
                        calls[lastIdx] = {
                          ...calls[lastIdx],
                          sources: event.sources as Source[] | undefined,
                          web_results: event.web_results as WebResult[] | undefined,
                          rows: event.rows as SqlRow[] | undefined,
                        }
                      }
                      return { ...sa, toolCalls: calls }
                    }),
                  }
                })
              )
            } else if (event.type === 'subagent_done') {
              setMessages(prev =>
                prev.map(m => {
                  if (m.id !== assistantId) return m
                  return {
                    ...m,
                    subAgents: (m.subAgents ?? []).map(sa =>
                      sa.id === event.id
                        ? { ...sa, summary: event.summary as string, isDone: true }
                        : sa
                    ),
                  }
                })
              )
            } else if (event.type === 'done') {
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? { ...m, id: event.message_id ?? m.id, isStreaming: false }
                    : m
                )
              )
              if (event.title) {
                onTitleChangeRef.current?.(currentThreadId, event.title)
              }
            } else if (event.type === 'error') {
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId ? { ...m, content: `Error: ${event.message}`, isStreaming: false } : m
                )
              )
            }
          } catch {
            // malformed SSE line — skip
          }
        }
      }
    } catch {
      setMessages(prev =>
        prev.map(m => {
          if (m.id !== assistantId) return m
          return {
            ...m,
            content: m.content || 'Failed to get response.',
            isStreaming: false,
            subAgents: (m.subAgents ?? []).map(sa =>
              sa.isDone ? sa : { ...sa, isDone: true }
            ),
          }
        })
      )
    } finally {
      setIsStreaming(false)
    }
  }, [threadId, session, isStreaming])

  return { messages, isStreaming, sendMessage }
}
