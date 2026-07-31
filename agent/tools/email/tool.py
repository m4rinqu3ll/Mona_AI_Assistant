"""Outlook email behavior exposed through the generic tool contract."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

from pydantic import BaseModel

from agent.clients.graph import MicrosoftGraphClient
from agent.models.tools import ExecutionContext
from agent.tools.base import BaseTool
from agent.tools.email.schemas import (
    DownloadAttachmentParameters,
    GetUnreadParameters,
    MessageIdParameters,
    ReplyEmailParameters,
    SearchParameters,
    SendEmailParameters,
)


class EmailTool(BaseTool):
    name = "email"
    description = "Read, search, send, reply to, and update the authenticated Outlook mailbox."
    action_schemas = MappingProxyType(
        {
            "get_unread": GetUnreadParameters,
            "read_email": MessageIdParameters,
            "search": SearchParameters,
            "send": SendEmailParameters,
            "reply": ReplyEmailParameters,
            "mark_read": MessageIdParameters,
            "download_attachment": DownloadAttachmentParameters,
        }
    )
    mutating_actions = frozenset({"send", "reply", "mark_read"})

    def __init__(self, graph_client: MicrosoftGraphClient) -> None:
        self._graph = graph_client

    async def _execute(
        self,
        action: str,
        parameters: BaseModel,
        context: ExecutionContext,
    ) -> Any:
        del context
        if action == "get_unread":
            values = self._as(parameters, GetUnreadParameters)
            return await self._graph.get_unread_messages(limit=values.limit)
        if action == "read_email":
            values = self._as(parameters, MessageIdParameters)
            return await self._graph.get_message(values.message_id)
        if action == "search":
            values = self._as(parameters, SearchParameters)
            return await self._graph.search_messages(query=values.query, limit=values.limit)
        if action == "send":
            values = self._as(parameters, SendEmailParameters)
            await self._graph.send_message(
                to=values.to,
                subject=values.subject,
                body=values.body,
                content_type=values.content_type,
                save_to_sent_items=values.save_to_sent_items,
            )
            return {"sent": True}
        if action == "reply":
            values = self._as(parameters, ReplyEmailParameters)
            await self._graph.reply_to_message(
                message_id=values.message_id,
                comment=values.comment,
            )
            return {"replied": True, "message_id": values.message_id}
        if action == "mark_read":
            values = self._as(parameters, MessageIdParameters)
            await self._graph.mark_message_read(message_id=values.message_id)
            return {"marked_read": True, "message_id": values.message_id}
        values = self._as(parameters, DownloadAttachmentParameters)
        attachment = await self._graph.get_attachment(
            message_id=values.message_id,
            attachment_id=values.attachment_id,
        )
        return attachment

    @staticmethod
    def _as(model: BaseModel, expected: type[BaseModel]) -> Any:
        if not isinstance(model, expected):
            raise TypeError(f"Expected {expected.__name__}, got {type(model).__name__}")
        return model

