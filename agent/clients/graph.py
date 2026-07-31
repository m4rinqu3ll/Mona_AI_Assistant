"""Least-privilege asynchronous Microsoft Graph client."""

from __future__ import annotations

import asyncio
import time
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import httpx

from agent.auth.microsoft import TokenProvider
from agent.exceptions import ExternalServiceError


class MicrosoftGraphClient:
    LIST_MESSAGE_FIELDS = "id,subject,sender,from,receivedDateTime,isRead,bodyPreview"
    MESSAGE_FIELDS = "id,subject,sender,from,toRecipients,receivedDateTime,isRead,bodyPreview,body"

    def __init__(
        self,
        token_provider: TokenProvider,
        *,
        base_url: str = "https://graph.microsoft.com/v1.0",
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token_provider = token_provider
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout_seconds)

    async def close(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def get_unread_messages(self, *, limit: int = 10) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 50)
        data = await self._request(
            "GET",
            "/me/messages",
            params={
                "$filter": "isRead eq false",
                "$select": self.LIST_MESSAGE_FIELDS,
                "$orderby": "receivedDateTime desc",
                "$top": str(limit),
            },
        )
        return list(data.get("value", []))

    async def get_message(self, message_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/me/messages/{self._id(message_id)}",
            params={"$select": self.MESSAGE_FIELDS},
        )

    async def search_messages(self, *, query: str, limit: int = 10) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 25)
        safe_query = query.replace('"', "")[:200]
        data = await self._request(
            "GET",
            "/me/messages",
            params={
                "$search": f'"{safe_query}"',
                "$select": self.LIST_MESSAGE_FIELDS,
                "$top": str(limit),
            },
            headers={"ConsistencyLevel": "eventual"},
        )
        return list(data.get("value", []))

    async def send_message(
        self,
        *,
        to: list[str],
        subject: str,
        body: str,
        content_type: str = "Text",
        save_to_sent_items: bool = True,
    ) -> None:
        await self._request(
            "POST",
            "/me/sendMail",
            json={
                "message": {
                    "subject": subject,
                    "body": {"contentType": content_type, "content": body},
                    "toRecipients": [
                        {"emailAddress": {"address": address}} for address in to
                    ],
                },
                "saveToSentItems": save_to_sent_items,
            },
        )

    async def reply_to_message(self, *, message_id: str, comment: str) -> None:
        await self._request(
            "POST",
            f"/me/messages/{self._id(message_id)}/reply",
            json={"comment": comment},
        )

    async def mark_message_read(self, *, message_id: str) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/me/messages/{self._id(message_id)}",
            json={"isRead": True},
        )

    async def get_attachment(
        self, *, message_id: str, attachment_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/me/messages/{self._id(message_id)}/attachments/{self._id(attachment_id)}",
            params={"$select": "id,name,contentType,size,isInline,contentBytes"},
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        token = await self._token_provider.get_access_token()
        request_headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        request_headers.update(headers or {})
        response: httpx.Response | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._http.request(
                    method,
                    f"{self._base_url}{path}",
                    params=params,
                    json=json,
                    headers=request_headers,
                )
            except httpx.RequestError as exc:
                if attempt >= self._max_retries:
                    raise ExternalServiceError(
                        "Microsoft Graph is currently unavailable.",
                        details={"service": "microsoft_graph"},
                    ) from exc
                await asyncio.sleep(2**attempt)
                continue
            if response.status_code not in {429, 500, 502, 503, 504}:
                break
            if attempt >= self._max_retries:
                break
            await asyncio.sleep(self._retry_delay(response, attempt))

        if response is None:
            raise ExternalServiceError("Microsoft Graph did not return a response.")
        if response.is_error:
            request_id = response.headers.get("request-id")
            try:
                graph_error = response.json().get("error", {})
                message = graph_error.get("message", "Microsoft Graph request failed.")
                code = graph_error.get("code", "graph_error")
            except ValueError:
                message, code = "Microsoft Graph request failed.", "graph_error"
            raise ExternalServiceError(
                message,
                details={
                    "status_code": response.status_code,
                    "code": code,
                    "request_id": request_id,
                },
            )
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return dict(response.json())
        except ValueError as exc:
            raise ExternalServiceError("Microsoft Graph returned invalid JSON.") from exc

    @staticmethod
    def _id(value: str) -> str:
        return quote(value, safe="")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 60.0)
            except ValueError:
                try:
                    delay = parsedate_to_datetime(retry_after).timestamp() - time.time()
                    return min(max(delay, 0.0), 60.0)
                except (TypeError, ValueError, OverflowError):
                    pass
        return min(float(2**attempt), 30.0)
