"""Explicit provider used when LLM integration is not configured."""

from __future__ import annotations

from typing import Any

from agent.exceptions import ConfigurationError
from agent.llm.base import LLMMessage, LLMProvider, LLMResponse


class DisabledLLMProvider(LLMProvider):
    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        del messages, tools
        raise ConfigurationError(
            "LLM integration is disabled. Set LLM_PROVIDER=openai and OPENAI_API_KEY."
        )

