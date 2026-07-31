"""Dependency composition root."""

from __future__ import annotations

from dataclasses import dataclass

from agent.auth.microsoft import MicrosoftAuthenticator
from agent.auth.token_store import KeyringTokenStore
from agent.clients.graph import MicrosoftGraphClient
from agent.config import Settings
from agent.dispatcher import ToolDispatcher
from agent.llm.base import LLMProvider
from agent.llm.deepseek_provider import DeepSeekProvider
from agent.llm.disabled_provider import DisabledLLMProvider
from agent.llm.openai_provider import OpenAIProvider
from agent.services.chat import ChatService
from agent.tools.email import EmailTool


class UnconfiguredTokenProvider:
    async def get_access_token(self) -> str:
        from agent.exceptions import ConfigurationError

        raise ConfigurationError("MS_CLIENT_ID is not configured.")


@dataclass(slots=True)
class Container:
    settings: Settings
    dispatcher: ToolDispatcher
    graph_client: MicrosoftGraphClient
    chat_service: ChatService
    authenticator: MicrosoftAuthenticator | None

    async def close(self) -> None:
        await self.graph_client.close()


def build_container(settings: Settings) -> Container:
    authenticator: MicrosoftAuthenticator | None = None
    token_provider: MicrosoftAuthenticator | UnconfiguredTokenProvider
    if settings.ms_client_id:
        authenticator = MicrosoftAuthenticator(
            client_id=settings.ms_client_id,
            authority=settings.ms_authority,
            scopes=settings.ms_scopes,
            token_store=KeyringTokenStore(settings.ms_token_keyring_service),
        )
        token_provider = authenticator
    else:
        token_provider = UnconfiguredTokenProvider()

    graph_client = MicrosoftGraphClient(
        token_provider,
        base_url=settings.graph_base_url,
        timeout_seconds=settings.graph_timeout_seconds,
        max_retries=settings.graph_max_retries,
    )
    dispatcher = ToolDispatcher(auto_approve=settings.auto_approve_tools)
    dispatcher.register(EmailTool(graph_client))

    provider: LLMProvider
    if settings.llm_provider == "deepseek" and settings.deepseek_api_key:
        provider = DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
            thinking=settings.deepseek_thinking,
        )
    elif settings.llm_provider == "openai" and settings.openai_api_key:
        provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            reasoning_effort=settings.openai_reasoning_effort,
        )
    else:
        provider = DisabledLLMProvider()
    chat_service = ChatService(
        provider,
        dispatcher,
        max_tool_steps=settings.llm_max_tool_steps,
    )
    return Container(settings, dispatcher, graph_client, chat_service, authenticator)
