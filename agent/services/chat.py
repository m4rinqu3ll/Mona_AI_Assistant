"""Reasoning loop that lets an LLM request tools without accessing APIs directly."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError

from agent.dispatcher import ToolDispatcher
from agent.llm.base import LLMMessage, LLMProvider, LLMToolCall
from agent.models.tools import ExecutionContext, ToolCall, ToolResult
from agent.prompts.system import SYSTEM_PROMPT
from agent.schemas.api import ChatHistoryMessage


@dataclass(frozen=True, slots=True)
class ChatOutcome:
    message: str
    tool_results: list[ToolResult]


class ChatService:
    def __init__(
        self,
        provider: LLMProvider,
        dispatcher: ToolDispatcher,
        *,
        max_tool_steps: int = 4,
    ) -> None:
        self._provider = provider
        self._dispatcher = dispatcher
        self._max_tool_steps = max_tool_steps

    async def chat(
        self,
        message: str,
        history: list[ChatHistoryMessage],
        context: ExecutionContext,
    ) -> ChatOutcome:
        messages = [LLMMessage(role="system", content=SYSTEM_PROMPT)]
        messages.extend(LLMMessage(role=item.role, content=item.content) for item in history)
        messages.append(LLMMessage(role="user", content=message))
        tool_results: list[ToolResult] = []
        definitions = self._tool_definitions()

        for _ in range(self._max_tool_steps):
            response = await self._provider.complete(messages, definitions)
            if not response.tool_calls:
                return ChatOutcome(
                    message=response.content or "The model returned an empty response.",
                    tool_results=tool_results,
                )
            messages.append(
                LLMMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )
            for requested in response.tool_calls:
                result = await self._dispatch_llm_call(requested, context)
                tool_results.append(result)
                messages.append(
                    LLMMessage(
                        role="tool",
                        name=requested.name,
                        tool_call_id=requested.id,
                        content=json.dumps(result.model_dump(mode="json"), default=str),
                    )
                )
                if result.approval_status.value in {"PENDING_APPROVAL", "REJECTED"}:
                    status = result.approval_status.value.replace("_", " ").lower()
                    return ChatOutcome(
                        message=f"The requested {result.tool}.{result.action} action is {status}.",
                        tool_results=tool_results,
                    )
        return ChatOutcome(
            message="The maximum number of tool steps was reached safely.",
            tool_results=tool_results,
        )

    async def _dispatch_llm_call(
        self,
        requested: LLMToolCall,
        context: ExecutionContext,
    ) -> ToolResult:
        arguments = requested.arguments
        action = arguments.get("action", "")
        parameters = arguments.get("parameters", {})
        try:
            call = ToolCall(tool=requested.name, action=action, parameters=parameters)
        except ValidationError as exc:
            from agent.models.tools import ToolError

            return ToolResult(
                success=False,
                tool=requested.name,
                action=str(action),
                correlation_id=context.correlation_id,
                error=ToolError(
                    code="invalid_llm_tool_call",
                    message="The LLM returned an invalid tool call.",
                    details={"validation_errors": exc.errors(include_url=False)},
                ),
            )
        return await self._dispatcher.dispatch(call, context)

    def _tool_definitions(self) -> list[dict[str, object]]:
        definitions: list[dict[str, object]] = []
        for manifest in self._dispatcher.manifests():
            actions = list(manifest["actions"])
            action_details = "; ".join(
                f"{name}: {details['parameters']}"
                for name, details in manifest["actions"].items()
            )
            definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": manifest["name"],
                        "description": f"{manifest['description']} Actions: {action_details}",
                        "parameters": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["action", "parameters"],
                            "properties": {
                                "action": {"type": "string", "enum": actions},
                                "parameters": {"type": "object"},
                            },
                        },
                    },
                }
            )
        return definitions
