import json
import uuid
from typing import AsyncGenerator
from app.services.llm_client import stream_chat_completion
from app.services.retrieval_service import search_documents
from app.services.web_search_service import search_web, is_web_search_enabled
from app.services.text_to_sql_service import query_documents_metadata, DocumentMetadataQuery

_SA_SYSTEM = (
    "You are a specialized research agent. You have been delegated a focused analysis task "
    "by the main assistant. You have access to all search tools. Make multiple searches to "
    "gather comprehensive information. You do NOT have access to the conversation history — "
    "your task description contains all necessary context. "
    "Be thorough. When you have gathered enough information, synthesize a complete answer."
)

_SA_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": "Hybrid semantic + keyword search over the user's uploaded documents.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "The search query"}},
            "required": ["query"],
        },
    },
}

_SA_METADATA_TOOL = {
    "type": "function",
    "function": {
        "name": "query_documents_metadata",
        "description": "Query structured metadata about the user's uploaded documents.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic_contains": {"type": "string"},
                "language": {"type": "string"},
                "status": {"type": "string", "enum": ["pending", "processing", "done", "error"]},
                "name_contains": {"type": "string"},
                "created_after": {"type": "string"},
                "order_by": {"type": "string", "enum": ["created_at", "name", "chunk_count"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": [],
        },
    },
}

_SA_WEB_TOOL = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the web for current or general knowledge.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "The web search query"}},
            "required": ["query"],
        },
    },
}


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


async def run_sub_agent(task: str, user_id: str) -> AsyncGenerator[dict, None]:
    agent_id = f"sa_{uuid.uuid4().hex[:8]}"
    yield {"type": "subagent_start", "id": agent_id, "task": task}

    messages = [
        {"role": "system", "content": _SA_SYSTEM},
        {"role": "user", "content": task},
    ]

    tools = [_SA_SEARCH_TOOL, _SA_METADATA_TOOL]
    if is_web_search_enabled():
        tools.append(_SA_WEB_TOOL)

    final_text = ""

    for _ in range(4):  # cap at 4 tool-call rounds
        full_text = ""
        tool_calls_raw: list[dict] = []
        last_finish_reason = None

        stream = await stream_chat_completion(messages, tools=tools)
        async for chunk in stream:
            choice = chunk.choices[0]
            delta = choice.delta
            if choice.finish_reason:
                last_finish_reason = choice.finish_reason

            if delta.content:
                full_text += delta.content
                yield {"type": "subagent_delta", "id": agent_id, "content": delta.content}

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

        final_text = full_text

        if last_finish_reason != "tool_calls" or not tool_calls_raw:
            break

        tool_results = []
        for tc in tool_calls_raw:
            tool_name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])

            if tool_name == "search_documents":
                query = args.get("query", "")
                yield {"type": "subagent_tool_call", "id": agent_id, "name": "search_documents", "query": query}
                chunks = await search_documents(query, user_id)
                yield {"type": "subagent_tool_result", "id": agent_id, "tool": "search_documents", "sources": chunks}
                tool_content = (
                    "\n\n".join(_format_chunk(c) for c in chunks)
                    if chunks else "No relevant documents found."
                )
                tool_results.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_content})

            elif tool_name == "query_documents_metadata":
                yield {"type": "subagent_tool_call", "id": agent_id, "name": "query_documents_metadata", "filters": args}
                params = DocumentMetadataQuery(**args)
                rows = await query_documents_metadata(params, user_id)
                yield {"type": "subagent_tool_result", "id": agent_id, "tool": "query_documents_metadata", "rows": rows}
                tool_content = (
                    "\n".join(f"- {r.get('name')}: {r.get('summary', '')}" for r in rows)
                    if rows else "No documents match the specified filters."
                )
                tool_results.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_content})

            elif tool_name == "search_web":
                query = args.get("query", "")
                yield {"type": "subagent_tool_call", "id": agent_id, "name": "search_web", "query": query}
                web_results = await search_web(query)
                yield {"type": "subagent_tool_result", "id": agent_id, "tool": "search_web", "web_results": web_results}
                tool_content = (
                    "\n\n".join(f"[{r['title']}]({r['url']})\n{r['content']}" for r in web_results)
                    if web_results else "No web results found."
                )
                tool_results.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_content})

        messages.append({"role": "assistant", "tool_calls": tool_calls_raw})
        messages.extend(tool_results)

    yield {"type": "subagent_done", "id": agent_id, "summary": final_text}
