from __future__ import annotations

import pytest

from agent.dispatcher import ToolDispatcher
from agent.llm.base import LLMResponse, LLMToolCall
from agent.models.tools import ExecutionContext
from agent.services.chat import ChatService
from agent.tools.email import EmailTool
from tests.fakes import FakeGraphClient, ScriptedLLM


@pytest.mark.asyncio
async def test_llm_can_only_reach_graph_through_dispatcher() -> None:
    graph = FakeGraphClient()
    dispatcher = ToolDispatcher()
    dispatcher.register(EmailTool(graph))  # type: ignore[arg-type]
    llm = ScriptedLLM(
        [
            LLMResponse(
                tool_calls=[
                    LLMToolCall(
                        id="call-1",
                        name="email",
                        arguments={"action": "get_unread", "parameters": {"limit": 1}},
                    )
                ]
            ),
            LLMResponse(content="You have one unread message."),
        ]
    )
    service = ChatService(llm, dispatcher)

    outcome = await service.chat("Any unread mail?", [], ExecutionContext())

    assert outcome.message == "You have one unread message."
    assert len(outcome.tool_results) == 1
    assert graph.calls == [("get_unread_messages", {"limit": 1})]
    assert llm.calls[1][0][-1].role == "tool"

