from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from agent.llm.base import LLMMessage
from agent.llm.openai_provider import OpenAIProvider


class FakeResponses:
    def __init__(self) -> None:
        self.request: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> Any:
        self.request = kwargs
        return SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="function_call",
                    call_id="call-1",
                    name="email",
                    arguments='{"action":"get_unread","parameters":{"limit":1}}',
                )
            ],
            output_text="",
        )


@pytest.mark.asyncio
async def test_responses_api_function_call_is_provider_neutral() -> None:
    responses = FakeResponses()
    client = SimpleNamespace(responses=responses)
    provider = OpenAIProvider(api_key="unused", model="gpt-5.6-sol", client=client)
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
    assert result.tool_calls[0].arguments["parameters"] == {"limit": 1}
    assert responses.request is not None
    assert responses.request["tools"][0]["name"] == "email"
    assert responses.request["reasoning"] == {"effort": "low"}

