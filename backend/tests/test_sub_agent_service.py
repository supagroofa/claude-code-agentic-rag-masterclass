import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# must import after mocks are patched
pytestmark = pytest.mark.asyncio


def _make_text_chunk(content: str, finish_reason: str = "stop"):
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = content
    chunk.choices[0].delta.tool_calls = None
    chunk.choices[0].finish_reason = finish_reason
    return chunk


def _make_tool_chunk(index: int, tool_id: str, name: str, arguments: str, finish_reason: str = "tool_calls"):
    chunk = MagicMock()
    tc = MagicMock()
    tc.index = index
    tc.id = tool_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = arguments
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = None
    chunk.choices[0].delta.tool_calls = [tc]
    chunk.choices[0].finish_reason = finish_reason
    return chunk


async def _async_gen(*items):
    for item in items:
        yield item


async def test_run_sub_agent_no_tools_yields_start_delta_done():
    """Sub-agent with a text-only response emits start → delta → done."""
    from app.services.sub_agent_service import run_sub_agent

    with patch("app.services.sub_agent_service.stream_chat_completion") as mock_scc, \
         patch("app.services.sub_agent_service.is_web_search_enabled", return_value=False):
        mock_scc.return_value = _async_gen(_make_text_chunk("Analysis complete.", "stop"))

        events = [e async for e in run_sub_agent("Summarize docs", "user_1")]

    types = [e["type"] for e in events]
    assert types[0] == "subagent_start"
    assert "subagent_delta" in types
    assert types[-1] == "subagent_done"
    assert events[0]["task"] == "Summarize docs"
    assert events[-1]["summary"] == "Analysis complete."


async def test_run_sub_agent_one_tool_call():
    """Sub-agent that calls search_documents once emits tool_call and tool_result events."""
    from app.services.sub_agent_service import run_sub_agent

    tool_chunk = _make_tool_chunk(0, "tc_1", "search_documents", '{"query": "revenue"}', "tool_calls")
    finish_chunk = _make_text_chunk("Found revenue data.", "stop")

    call_count = 0

    async def mock_scc(messages, tools=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _async_gen(tool_chunk)
        return _async_gen(finish_chunk)

    mock_chunks = [{"content": "Revenue was $10M", "similarity": 0.9,
                    "document_name": "report.pdf", "document_topics": [], "document_summary": None}]

    with patch("app.services.sub_agent_service.stream_chat_completion", mock_scc), \
         patch("app.services.sub_agent_service.is_web_search_enabled", return_value=False), \
         patch("app.services.sub_agent_service.search_documents", AsyncMock(return_value=mock_chunks)):

        events = [e async for e in run_sub_agent("Find revenue figures", "user_1")]

    types = [e["type"] for e in events]
    assert types[0] == "subagent_start"
    assert "subagent_tool_call" in types
    assert "subagent_tool_result" in types
    assert types[-1] == "subagent_done"

    tool_call_event = next(e for e in events if e["type"] == "subagent_tool_call")
    assert tool_call_event["name"] == "search_documents"
    assert tool_call_event["query"] == "revenue"

    tool_result_event = next(e for e in events if e["type"] == "subagent_tool_result")
    assert tool_result_event["tool"] == "search_documents"
    assert len(tool_result_event["sources"]) == 1
