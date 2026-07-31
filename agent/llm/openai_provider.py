"""OpenAI implementation of the provider-neutral LLM interface."""

from __future__ import annotations

import json
from typing import Any

from agent.exceptions import ExternalServiceError
from agent.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMToolCall


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        reasoning_effort: str = "low",
        client: Any | None = None,
    ) -> None:
        if client is None:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._client: Any = client
        self._model = model
        self._reasoning_effort = reasoning_effort

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        try:
            responses_create: Any = self._client.responses.create
            response = await responses_create(
                model=self._model,
                input=self._to_response_input(messages),
                tools=self._to_response_tools(tools),
                tool_choice="auto",
                reasoning={"effort": self._reasoning_effort},
            )
        except Exception as exc:
            raise ExternalServiceError(
                "The configured LLM provider is unavailable.",
                details={"provider": "openai"},
            ) from exc
        tool_calls: list[LLMToolCall] = []
        for item in response.output:
            if item.type != "function_call":
                continue
            try:
                arguments = json.loads(item.arguments or "{}")
            except json.JSONDecodeError as exc:
                raise ExternalServiceError("The LLM returned invalid tool arguments.") from exc
            tool_calls.append(
                LLMToolCall(id=item.call_id, name=item.name, arguments=arguments)
            )
        return LLMResponse(content=response.output_text or None, tool_calls=tool_calls)

    @staticmethod
    def _to_response_input(messages: list[LLMMessage]) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "tool":
                payload.append(
                    {
                        "type": "function_call_output",
                        "call_id": message.tool_call_id,
                        "output": message.content or "",
                    }
                )
                continue
            if message.content or not message.tool_calls:
                payload.append({"role": message.role, "content": message.content or ""})
            payload.extend(
                {
                    "type": "function_call",
                    "call_id": call.id,
                    "name": call.name,
                    "arguments": json.dumps(call.arguments),
                }
                for call in message.tool_calls
            )
        return payload

    @staticmethod
    def _to_response_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {"type": "function", **tool["function"]}
            for tool in tools
            if tool.get("type") == "function"
        ]
