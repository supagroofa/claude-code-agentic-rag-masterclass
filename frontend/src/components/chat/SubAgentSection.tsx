import { useState } from 'react'
import { cn } from '@/lib/utils'
import type { SubAgent } from '@/types'

interface Props {
  agent: SubAgent
}

export function SubAgentSection({ agent }: Props) {
  const [isOpen, setIsOpen] = useState(true)

  const taskLabel = agent.task

  return (
    <div className="mt-2 rounded-lg border border-purple-200 dark:border-purple-800 bg-purple-50 dark:bg-purple-950/30">
      <button
        onClick={() => setIsOpen(prev => !prev)}
        aria-expanded={isOpen}
        className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-purple-100 dark:hover:bg-purple-900/20 rounded-lg transition-colors"
      >
        <svg
          className="w-3.5 h-3.5 text-purple-500 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15M14.25 3.104c.251.023.501.05.75.082M19.8 15l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.5l1.196 4.783A2.25 2.25 0 0118.8 21.75H5.2a2.25 2.25 0 01-2.196-1.967L4 14.5"
          />
        </svg>
        <span className="text-xs font-semibold text-purple-700 dark:text-purple-300 flex-1 truncate">
          Sub-Agent: {taskLabel}
        </span>
        {!agent.isDone && (
          <span className="text-xs text-purple-400 animate-pulse shrink-0">working…</span>
        )}
        <svg
          className={cn('w-3.5 h-3.5 text-purple-400 shrink-0 transition-transform', isOpen && 'rotate-180')}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="px-3 pb-3 space-y-2">
          {agent.reasoning && (
            <p className="text-xs text-purple-600 dark:text-purple-300 italic leading-relaxed">
              {agent.reasoning}
              {!agent.isDone && (
                <span className="inline-block w-1.5 h-3 ml-0.5 bg-purple-400 animate-pulse rounded-sm align-middle" />
              )}
            </p>
          )}

          {agent.toolCalls.map((tc, i) => (
            <div
              key={i}
              className="rounded border border-purple-200 dark:border-purple-700 bg-white dark:bg-gray-800 px-2.5 py-2"
            >
              <p className="text-xs font-mono text-purple-600 dark:text-purple-400 mb-1">
                {tc.name}
                {tc.query
                  ? `("${tc.query}")`
                  : tc.filters && Object.keys(tc.filters).length > 0
                  ? `(${JSON.stringify(tc.filters)})`
                  : '()'}
              </p>
              {tc.sources && tc.sources.length > 0 && (
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  {tc.sources.length} source{tc.sources.length !== 1 ? 's' : ''} found
                </p>
              )}
              {tc.web_results && tc.web_results.length > 0 && (
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  {tc.web_results.length} web result{tc.web_results.length !== 1 ? 's' : ''} found
                </p>
              )}
              {tc.rows && tc.rows.length > 0 && (
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  {tc.rows.length} document{tc.rows.length !== 1 ? 's' : ''} found
                </p>
              )}
              {!tc.sources && !tc.web_results && !tc.rows && (
                <span className="inline-block w-1.5 h-3 bg-purple-300 dark:bg-purple-600 animate-pulse rounded-sm" />
              )}
            </div>
          ))}

          {agent.isDone && agent.summary && (
            <div className="rounded border border-purple-200 dark:border-purple-700 bg-purple-100 dark:bg-purple-900/40 px-2.5 py-2">
              <p className="text-xs font-semibold text-purple-700 dark:text-purple-300 mb-1">Summary</p>
              <p className="text-xs text-purple-700 dark:text-purple-200 leading-relaxed line-clamp-6">
                {agent.summary}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
