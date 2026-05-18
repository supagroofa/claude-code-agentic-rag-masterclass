import json
import uuid
from datetime import date
from typing import AsyncGenerator
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.dependencies import get_current_user
from app.models.schemas import ChatRequest
from app.services.supabase_client import supabase_admin
from app.services.llm_client import stream_chat_completion, generate_title
from app.services.retrieval_service import search_documents
from app.services.web_search_service import search_web, is_web_search_enabled
from app.services.text_to_sql_service import query_documents_metadata, DocumentMetadataQuery
from app.services.sub_agent_service import run_sub_agent

router = APIRouter()

MAX_HISTORY_MESSAGES = 20


def _format_chunk(c: dict) -> str:
    header = f"[Source: {c['document_name']}"
    if c.get("document_topics"):
        header += f" | Topics: {', '.join(c['document_topics'])}"
    header += "]"
    parts = [header]
    if c.get("document_summary"):
        parts.append(f"Summary: {c['document_summary']}")
    parts.append(f"\nRelevant excerpt:\n{c['content']}")
    return "\n".join(parts)


_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": (
            "Hybrid semantic + keyword search over the user's uploaded documents. "
            "Use first when the question may be answered by document content."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"],
        },
    },
}

_METADATA_TOOL = {
    "type": "function",
    "function": {
        "name": "query_documents_metadata",
        "description": (
            "Query structured metadata about the user's uploaded documents. "
            "Use when the user asks about document inventory or properties "
            "(e.g. 'what files do I have?', 'how many English documents?', 'show me recent uploads'). "
            "Do NOT use for content questions — use search_documents for that."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic_contains": {
                    "type": "string",
                    "description": "Exact topic string to filter on",
                },
                "language": {
                    "type": "string",
                    "description": "ISO 639-1 code, e.g. 'en', 'fr'",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "processing", "done", "error"],
                },
                "name_contains": {
                    "type": "string",
                    "description": "Filename substring (case-insensitive)",
                },
                "created_after": {
                    "type": "string",
                    "description": "ISO 8601 date, e.g. '2025-01-01'",
                },
                "order_by": {
                    "type": "string",
                    "enum": ["created_at", "name", "chunk_count"],
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": [],
        },
    },
}

_WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": (
            "Search the web for current, real-time, or general knowledge "
            "unlikely to be in the user's uploaded documents. "
            "Use as a fallback when search_documents returns nothing relevant, "
            "or when the user asks about current events."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The web search query"}
            },
            "required": ["query"],
        },
    },
}

_DELEGATE_TOOL = {
    "type": "function",
    "function": {
        "name": "delegate_to_subagent",
        "description": (
            "Delegate a complex, context-heavy research task to an isolated sub-agent with fresh context "
            "and multi-round search capability. Use when the task requires exhaustive search and synthesis "
            "across many document chunks (e.g. 'summarize everything about X', 'find all mentions of Z', "
            "'compare documents on Y'). The sub-agent has no access to conversation history — include all "
            "necessary context in the task description."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "A complete, self-contained task description with all context the sub-agent needs.",
                }
            },
            "required": ["task"],
        },
    },
}


def _build_system_prompt(web_search_available: bool) -> str:
    today = date.today().isoformat()
    prompt = (
        f"You are a helpful assistant. Today's date is {today}.\n\n"
        "You have access to the following tools:\n\n"
        "1. **search_documents** — searches content inside the user's uploaded documents.\n"
        "2. **query_documents_metadata** — queries document inventory (names, topics, language, status, dates).\n"
        "3. **delegate_to_subagent** — delegates a focused research task to a sub-agent with fresh context "
        "and multi-round search capability.\n"
    )
    if web_search_available:
        prompt += "4. **search_web** — searches the web for current or general information.\n"
    prompt += (
        "\nRouting guidance:\n"
        "- Questions about content inside documents → search_documents\n"
        "- Questions about what documents exist or their properties → query_documents_metadata\n"
        "- Tasks requiring exhaustive multi-search synthesis (e.g. 'summarize everything about X', "
        "'find all mentions of Z') → delegate_to_subagent\n"
    )
    if web_search_available:
        prompt += (
            "- General knowledge or current events not in documents → search_web\n"
            "- You may call multiple tools in parallel when useful.\n"
        )
    prompt += "Always cite your sources: document name for docs, URL for web results."
    return prompt


def _build_messages(history: list[dict], new_user_content: str, web_search_available: bool) -> list[dict]:
    system = {"role": "system", "content": _build_system_prompt(web_search_available)}
    trimmed = history[-MAX_HISTORY_MESSAGES:]
    msgs = [system] + [{"role": r["role"], "content": r["content"]} for r in trimmed]
    msgs.append({"role": "user", "content": new_user_content})
    return msgs


async def _stream_chat(thread_id: str, content: str, user_id: str) -> AsyncGenerator[str, None]:
    thread = (
        supabase_admin.table("threads")
        .select("id,user_renamed")
        .eq("id", thread_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not thread.data:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Thread not found'})}\n\n"
        return

    user_renamed = thread.data.get("user_renamed", False)

    history_result = (
        supabase_admin.table("messages")
        .select("role,content")
        .eq("thread_id", thread_id)
        .order("created_at")
        .execute()
    )
    history = history_result.data or []
    is_first_message = len(history) == 0

    supabase_admin.table("messages").insert({
        "thread_id": thread_id,
        "user_id": user_id,
        "role": "user",
        "content": content,
    }).execute()

    web_search_available = is_web_search_enabled()
    tools = [_SEARCH_TOOL, _METADATA_TOOL, _DELEGATE_TOOL]
    if web_search_available:
        tools.append(_WEB_SEARCH_TOOL)

    messages = _build_messages(history, content, web_search_available)
    full_text = ""
    tool_calls_raw: list[dict] = []

    try:
        stream = await stream_chat_completion(messages, tools=tools)
        last_finish_reason = None

        async for chunk in stream:
            choice = chunk.choices[0]
            delta = choice.delta
            if choice.finish_reason:
                last_finish_reason = choice.finish_reason

            if delta.content:
                full_text += delta.content
                yield f"data: {json.dumps({'type': 'delta', 'content': delta.content})}\n\n"

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    while len(tool_calls_raw) <= tc.index:
                        tool_calls_raw.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                    if tc.id:
                        tool_calls_raw[tc.index]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_raw[tc.index]["function"]["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_raw[tc.index]["function"]["arguments"] += tc.function.arguments

        if last_finish_reason == "tool_calls" and tool_calls_raw:
            tool_results = []

            for tc in tool_calls_raw:
                tool_name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])

                if tool_name == "search_documents":
                    query = args.get("query", "")
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': 'search_documents', 'query': query})}\n\n"

                    chunks = await search_documents(query, user_id)
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'search_documents', 'sources': chunks})}\n\n"

                    tool_content = (
                        "\n\n".join(_format_chunk(c) for c in chunks)
                        if chunks
                        else "No relevant documents found."
                    )
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_content,
                    })

                elif tool_name == "query_documents_metadata":
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': 'query_documents_metadata', 'filters': args})}\n\n"

                    params = DocumentMetadataQuery(**args)
                    rows = await query_documents_metadata(params, user_id)
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'query_documents_metadata', 'rows': rows})}\n\n"

                    if rows:
                        tool_content = "\n".join(
                            f"- {r.get('name')} | status: {r.get('status')} | language: {r.get('language')} "
                            f"| topics: {', '.join(r.get('topics') or [])} | chunks: {r.get('chunk_count')} "
                            f"| created: {r.get('created_at', '')[:10]}"
                            for r in rows
                        )
                    else:
                        tool_content = "No documents match the specified filters."
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_content,
                    })

                elif tool_name == "search_web":
                    query = args.get("query", "")
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': 'search_web', 'query': query})}\n\n"

                    web_results = await search_web(query)
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'search_web', 'web_results': web_results})}\n\n"

                    tool_content = (
                        "\n\n".join(f"[{r['title']}]({r['url']})\n{r['content']}" for r in web_results)
                        if web_results
                        else "No web results found."
                    )
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_content,
                    })

                elif tool_name == "delegate_to_subagent":
                    task = args.get("task", "")
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': 'delegate_to_subagent', 'task': task})}\n\n"

                    subagent_summary = ""
                    async for sa_event in run_sub_agent(task, user_id):
                        if sa_event["type"] == "subagent_done":
                            subagent_summary = sa_event.get("summary", "")
                        yield f"data: {json.dumps(sa_event)}\n\n"

                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": subagent_summary or "Sub-agent completed the analysis.",
                    })

            messages.append({"role": "assistant", "tool_calls": tool_calls_raw})
            messages.extend(tool_results)

            # Second pass: no tools — LLM synthesises from tool results only.
            # Sub-agents handle multi-round retrieval; main agent always ends here.
            stream2 = await stream_chat_completion(messages)
            async for chunk in stream2:
                delta = chunk.choices[0].delta
                if delta.content:
                    full_text += delta.content
                    yield f"data: {json.dumps({'type': 'delta', 'content': delta.content})}\n\n"

        message_result = supabase_admin.table("messages").insert({
            "thread_id": thread_id,
            "user_id": user_id,
            "role": "assistant",
            "content": full_text,
        }).execute()

        message_id = message_result.data[0]["id"] if message_result.data else str(uuid.uuid4())

        new_title = None
        if is_first_message and not user_renamed:
            try:
                new_title = await generate_title(content)
                supabase_admin.table("threads").update({"title": new_title}).eq("id", thread_id).execute()
            except Exception:
                pass

        yield f"data: {json.dumps({'type': 'done', 'message_id': message_id, 'title': new_title})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@router.post("/stream")
async def chat_stream(body: ChatRequest, user: dict = Depends(get_current_user)):
    return StreamingResponse(
        _stream_chat(body.thread_id, body.content, user["sub"]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
