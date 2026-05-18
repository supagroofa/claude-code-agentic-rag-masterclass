# Progress

Track your progress through the masterclass. Update this file as you complete modules - Claude Code reads this to understand where you are in the project.

## Convention
- `[ ]` = Not started
- `[-]` = In progress
- `[x]` = Completed

## Modules

### Module 1: App Shell + Observability
**Status:** `[x]` Complete — all phases validated

**Bugs fixed during validation:**
1. **ES256 JWTs** — newer Supabase projects sign user tokens with ECDSA not HS256. Switched `dependencies.py` to `supabase_admin.auth.get_user(token)` instead of `jose.jwt.decode()`.
2. **MouseEvent passed as thread title** — `onNew={createThread}` let React pass the click event as the first argument. Fixed to `onNew={() => createThread()}`.
3. **Auth state not shared** — each `useAuth()` call created an independent instance. Moved auth state into a shared `AuthContext` so session is never null when protected pages render.
4. **Streaming blocked the event loop** — synchronous `for event in stream:` inside an async generator prevented uvicorn from flushing SSE bytes mid-response. Switched to `AsyncOpenAI` with `async for`.
5. **`file_search` requires `vector_store_ids`** — OpenAI now rejects the tool without a vector store. Removed for Module 1; will be added back with a real vector store in Module 2.

**Note on LangSmith tracing:** env vars are configured (`LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`). The `@traceable` decorator was removed from the streaming function because it buffered the async iterator. Proper tracing will be wired in Module 2 using `wrap_openai` or a non-blocking trace wrapper.

**Start commands:**
```bash
# Backend (from project root)
cd backend && venv/Scripts/activate && uvicorn app.main:app --reload

# Frontend (from project root)
cd frontend && npm run dev
```

### Module 2: BYO Retrieval + Memory
**Status:** `[x]` Complete — all sub-plans validated

**Sub-plans:**
- `[x]` 2.provider-abstraction — Chat Completions API, dual provider config, stateless history
- `[x]` 3.document-ingestion — File upload, chunking, embeddings, pgvector
- `[x]` 4.retrieval-tool — Vector search, tool calling loop
- `[x]` 5.ingestion-ui — Frontend upload UI, Realtime status

**Changes in sub-plan 2:**
- Replaced OpenAI Responses API with standard Chat Completions API
- `LLM_*` env vars for chat provider (OpenRouter/Ollama/LM Studio/OpenAI)
- `EMBEDDING_*` env vars for embedding provider (independent from chat)
- `dimensions` kwarg auto-omitted for non-OpenAI embedding providers
- Chat history fetched from DB and sent as `messages[]` array (stateless)
- LangSmith tracing via `wrap_openai` (SSE-safe, non-blocking)
- Migration 003: removed `openai_response_id` from threads + messages

**Start commands:**
```bash
# Backend (from project root)
cd backend && source venv/Scripts/activate && uvicorn app.main:app --reload

# Frontend (from project root)
cd frontend && npm run dev
```

### Module 3: Record Manager
**Status:** `[x]` Complete — all sub-plans validated

**Sub-plans:**
- `[x]` 6.record-manager — Content-hash dedup, source-key update, purge on re-upload

**Bug fixed during validation:**
- **Stale UI row on source-key replacement** — Realtime only subscribes to `UPDATE` events, so server-side `purge_document` DELETE was never reflected in local state. Fixed by filtering on both `id` and `name` when prepending the new document in `useDocuments.upload()`.

---

## Module 4: Metadata Extraction
**Status:** `[x]` Complete — all phases validated

**Sub-plans:**
- `[x]` 7.metadata-extraction — LLM extraction of title/summary/topics/language, retrieval context enrichment, topic pill UI

---

## Module 5: Multi-Format Support
**Status:** `[x]` Complete — all phases validated

**Sub-plans:**
- `[x]` 8.multi-format-support — PDF/DOCX extraction via pypdf + python-docx, dynamic content-type, DropZone accept update

---

## Module 6: Hybrid Search & Reranking
**Status:** `[x]` Complete — all phases validated

**Sub-plans:**
- `[x]` 9.hybrid-search-reranking — FTS tsvector column, RRF fusion RPC, Cohere reranking (opt-in)

**Changes:**
- Migration 008: `chunks.fts` stored generated column (tsvector), GIN index, `hybrid_search_chunks` RPC (RRF fusion)
- `retrieval_service.py`: replaced `match_chunks` call with `hybrid_search_chunks`; reranking via `rerank_chunks`
- `reranker_service.py` (new): Cohere `AsyncClientV2`; no-op fallback when `COHERE_API_KEY` absent
- `config.py`: added `match_count`, `rrf_k`, `cohere_api_key`, `reranker_model`, `rerank_top_n`
- `main.py`: added `init_reranker()` startup call
- `requirements.txt`: added `cohere>=5.0.0` (installed: 6.1.0)

---

## Module 7: Additional Tools
**Status:** `[x]` Complete — all validation steps passed

**Sub-plans:**
- `[x]` 10.additional-tools — `query_documents_metadata` (structured filter query on documents table), `search_web` (Tavily fallback), parallel single-pass tool calling

**Changes:**
- `web_search_service.py` (new): Tavily `AsyncTavilyClient` wrapper; `init_web_search()` startup call; graceful no-op when `TAVILY_API_KEY` absent
- `text_to_sql_service.py` (new): `DocumentMetadataQuery` Pydantic model; Supabase chained filter API (no raw SQL); user_id always applied first
- `config.py`: added `tavily_api_key: Optional[str] = None`
- `main.py`: added `init_web_search()` startup call
- `routers/chat.py`: 3 tool definitions (`_SEARCH_TOOL`, `_METADATA_TOOL`, `_WEB_SEARCH_TOOL`); dynamic TOOLS list (web tool excluded if no API key); `_build_system_prompt()` with routing guidance; 3-way dispatch in tool loop; `tool_result` SSE events now include `tool` discriminator
- `requirements.txt`: added `tavily-python>=0.5.0`
- `frontend/src/types/index.ts`: added `WebResult`, `SqlRow` interfaces; `Message` extended with `web_results?` and `sql_rows?`
- `frontend/src/hooks/useChat.ts`: `tool_result` handler now dispatches on `event.tool`, appends (not overwrites) for parallel calls
- `frontend/src/components/chat/MessageItem.tsx`: "Web Results" section (clickable URLs) and "Documents Found" section (status badges, topic pills)

**Start commands:**
```bash
# Backend (from project root)
cd backend && venv/Scripts/activate && uvicorn app.main:app --reload

# Frontend (from project root)
cd frontend && npm run dev
```

---

## Module 8: Sub-Agents
**Status:** `[x]` Complete — all phases validated

**Sub-plans:**
- `[x]` 11.sub-agents — delegate_to_subagent tool, isolated multi-round sub-agent loop, nested SSE events, SubAgentSection UI

**Changes:**
- `sub_agent_service.py` (new): isolated async generator tool loop; 5 SSE event types (`subagent_start/delta/tool_call/tool_result/done`); max 4 tool-call rounds; `AsyncGenerator[dict, None]` type
- `chat.py`: `_DELEGATE_TOOL` definition; `run_sub_agent` handler in tool dispatch; updated `_build_system_prompt` with delegation routing guidance; documented second-pass no-tools constraint
- `types/index.ts`: `SubAgentToolCall`, `SubAgent` interfaces (`reasoning?/summary?` optional for streaming); `Message.subAgents` field
- `useChat.ts`: handlers for all 5 `subagent_*` events; guard on missing `event.id`; marks in-progress sub-agents done on stream abort
- `SubAgentSection.tsx` (new): collapsible purple card; aria-expanded/aria-hidden accessibility; streaming reasoning, tool call list with result counts, summary
- `MessageItem.tsx`: renders `message.subAgents` array above sources/web/sql sections

**Start commands:**
```bash
# Backend (from project root)
cd backend && venv/Scripts/activate && uvicorn app.main:app --reload

# Frontend (from project root)
cd frontend && npm run dev
```