import ReactMarkdown from 'react-markdown'
import { cn } from '@/lib/utils'
import type { Message } from '@/types'
import { SubAgentSection } from './SubAgentSection'

interface Props {
  message: Message
}

export function MessageItem({ message }: Props) {
  const isUser = message.role === 'user'
  const sources = !isUser ? (message.sources ?? []) : []
  const webResults = !isUser ? (message.web_results ?? []) : []
  const sqlRows = !isUser ? (message.sql_rows ?? []) : []

  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[75%] rounded-2xl px-4 py-2 text-sm leading-relaxed break-words',
          isUser
            ? 'bg-blue-600 text-white rounded-br-sm whitespace-pre-wrap'
            : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-sm'
        )}
      >
        {isUser ? (
          message.content
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none prose-a:text-blue-600 dark:prose-a:text-blue-400 prose-a:underline">
            <ReactMarkdown
              components={{
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer">
                    {children}
                  </a>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
            {message.isStreaming && (
              <span className="inline-block w-2 h-4 ml-0.5 bg-current animate-pulse rounded-sm" />
            )}
          </div>
        )}

        {!isUser && message.isStreaming && !message.content && (
          <span className="inline-block w-2 h-4 bg-current animate-pulse rounded-sm" />
        )}

        {!isUser && message.subAgents && message.subAgents.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
            <p className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-2">
              Sub-Agents
            </p>
            {message.subAgents.map(agent => (
              <SubAgentSection key={agent.id} agent={agent} />
            ))}
          </div>
        )}

        {sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
            <p className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-2">
              Sources
            </p>
            <div className="flex flex-col gap-1.5">
              {sources.map((source, i) => (
                <div
                  key={i}
                  className="rounded-lg bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 px-3 py-2"
                >
                  <p className="text-xs font-medium text-gray-700 dark:text-gray-200 truncate">
                    {source.document_title ?? source.document_name}
                  </p>
                  <p className="text-xs text-gray-400 dark:text-gray-400 mt-0.5 line-clamp-2">
                    {source.content.length > 120 ? source.content.slice(0, 120) + '…' : source.content}
                  </p>
                  <p className="text-xs text-gray-300 dark:text-gray-500 mt-1">
                    {source.rerank_score != null
                      ? `relevance ${source.rerank_score}`
                      : `similarity ${source.similarity}`}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {webResults.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
            <p className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-2">
              Web Results
            </p>
            <div className="flex flex-col gap-1.5">
              {webResults.map((result, i) => (
                <div
                  key={i}
                  className="rounded-lg bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 px-3 py-2"
                >
                  <a
                    href={result.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline truncate block"
                  >
                    {result.title || result.url}
                  </a>
                  <p className="text-xs text-gray-400 dark:text-gray-400 mt-0.5 line-clamp-2">
                    {result.content.length > 120 ? result.content.slice(0, 120) + '…' : result.content}
                  </p>
                  <p className="text-xs text-gray-300 dark:text-gray-500 mt-1">
                    score {result.score}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {sqlRows.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
            <p className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-2">
              Documents Found
            </p>
            <div className="flex flex-col gap-1.5">
              {sqlRows.map((row, i) => (
                <div
                  key={i}
                  className="rounded-lg bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 px-3 py-2"
                >
                  <p className="text-xs font-medium text-gray-700 dark:text-gray-200 truncate">
                    {row.title ?? row.name}
                  </p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {row.language && (
                      <span className="text-xs bg-gray-100 dark:bg-gray-600 text-gray-500 dark:text-gray-300 rounded px-1.5 py-0.5">
                        {row.language}
                      </span>
                    )}
                    <span
                      className={cn(
                        'text-xs rounded px-1.5 py-0.5',
                        row.status === 'done'
                          ? 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300'
                          : 'bg-yellow-100 dark:bg-yellow-900 text-yellow-700 dark:text-yellow-300'
                      )}
                    >
                      {row.status}
                    </span>
                    {row.chunk_count != null && (
                      <span className="text-xs text-gray-400 dark:text-gray-500">
                        {row.chunk_count} chunks
                      </span>
                    )}
                  </div>
                  {row.topics && row.topics.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {row.topics.slice(0, 3).map((topic, j) => (
                        <span
                          key={j}
                          className="text-xs bg-blue-50 dark:bg-blue-900 text-blue-600 dark:text-blue-300 rounded px-1.5 py-0.5"
                        >
                          {topic}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
