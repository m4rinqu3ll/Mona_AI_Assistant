from __future__ import annotations

from typing import Any

from agent.llm.base import LLMMessage, LLMProvider, LLMResponse


class FakeGraphClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def get_unread_messages(self, *, limit: int = 10) -> list[dict[str, Any]]:
        self.calls.append(("get_unread_messages", {"limit": limit}))
        return [{"id": "one", "subject": "Hello"}]

    async def get_message(self, message_id: str) -> dict[str, Any]:
        self.calls.append(("get_message", {"message_id": message_id}))
        return {"id": message_id}

    async def search_messages(self, *, query: str, limit: int = 10) -> list[dict[str, Any]]:
        self.calls.append(("search_messages", {"query": query, "limit": limit}))
        return []

    async def send_message(self, **kwargs: Any) -> None:
        self.calls.append(("send_message", kwargs))

    async def reply_to_message(self, **kwargs: Any) -> None:
        self.calls.append(("reply_to_message", kwargs))

    async def mark_message_read(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("mark_message_read", kwargs))
        return {"isRead": True}

    async def get_attachment(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("get_attachment", kwargs))
        return {"id": kwargs["attachment_id"], "name": "file.txt"}


class ScriptedLLM(LLMProvider):
    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[list[LLMMessage], list[dict[str, Any]]]] = []

    async def complete(
        self, messages: list[LLMMessage], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        self.calls.append((list(messages), tools))
        return self.responses.pop(0)

