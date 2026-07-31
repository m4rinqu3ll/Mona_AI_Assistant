from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from agent.llm.base import LLMMessage, LLMToolCall
from agent.llm.deepseek_provider import DeepSeekProvider


class FakeCompletions:
    def __init__(self) -> None:
        self.request: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> Any:
        self.request = kwargs
        function = SimpleNamespace(
            name="email",
            arguments='{"action":"get_unread","parameters":{"limit":3}}',
        )
        tool_call = SimpleNamespace(id="call-1", function=function)
        message = SimpleNamespace(content=None, tool_calls=[tool_call])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.mark.asyncio
async def test_deepseek_chat_completion_maps_tool_calls() -> None:
    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = DeepSeekProvider(api_key="unused", client=client)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "email",
                "description": "Email actions",
                "parameters": {"type": "object"},
            },
        }
    ]

    result = await provider.complete([LLMMessage(role="user", content="Unread?")], tools)

    assert result.tool_calls[0].name == "email"
    assert result.tool_calls[0].arguments["parameters"] == {"limit": 3}
    assert completions.request is not None
    assert completions.request["model"] == "deepseek-v4-flash"
    assert completions.request["extra_body"] == {"thinking": {"type": "disabled"}}


def test_deepseek_maps_tool_result_messages() -> None:
    message = LLMMessage(
        role="assistant",
        tool_calls=[
            LLMToolCall(
                id="call-1",
                name="email",
                arguments={"action": "get_unread", "parameters": {"limit": 1}},
            )
        ],
    )
    payload = DeepSeekProvider._to_chat_message(message)
    assert payload["tool_calls"][0]["function"]["name"] == "email"
