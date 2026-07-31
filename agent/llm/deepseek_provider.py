"""DeepSeek implementation using its OpenAI-compatible Chat Completions API."""

from __future__ import annotations

import json
from typing import Any

from agent.exceptions import ExternalServiceError
from agent.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMToolCall


class DeepSeekProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "deepseek-v4-flash",
        base_url: str = "https://api.deepseek.com",
        thinking: bool = False,
        client: Any | None = None,
    ) -> None:
        if client is None:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._client: Any = client
        self._model = model
        self._thinking = thinking

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        try:
            completion_create: Any = self._client.chat.completions.create
            response = await completion_create(
                model=self._model,
                messages=[self._to_chat_message(message) for message in messages],
                tools=tools or None,
                tool_choice="auto" if tools else None,
                stream=False,
                extra_body={
                    "thinking": {"type": "enabled" if self._thinking else "disabled"}
                },
            )
        except Exception as exc:
            raise ExternalServiceError(
                "The configured LLM provider is unavailable.",
                details={"provider": "deepseek"},
            ) from exc

        message = response.choices[0].message
        tool_calls: list[LLMToolCall] = []
        for call in message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError as exc:
                raise ExternalServiceError("The LLM returned invalid tool arguments.") from exc
            tool_calls.append(
                LLMToolCall(id=call.id, name=call.function.name, arguments=arguments)
            )
        return LLMResponse(content=message.content, tool_calls=tool_calls)

    @staticmethod
    def _to_chat_message(message: LLMMessage) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.name:
            payload["name"] = message.name
        if message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments),
                    },
                }
                for call in message.tool_calls
            ]
        return payload
