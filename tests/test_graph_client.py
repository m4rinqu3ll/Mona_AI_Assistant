from __future__ import annotations

import httpx
import pytest

from agent.clients.graph import MicrosoftGraphClient


class StaticTokenProvider:
    async def get_access_token(self) -> str:
        return "test-token"


@pytest.mark.asyncio
async def test_unread_request_is_bounded_and_selective() -> None:
    observed: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed
        observed = request
        return httpx.Response(200, json={"value": [{"id": "1"}]})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    graph = MicrosoftGraphClient(StaticTokenProvider(), http_client=http)

    messages = await graph.get_unread_messages(limit=500)

    assert messages == [{"id": "1"}]
    assert observed is not None
    assert observed.headers["Authorization"] == "Bearer test-token"
    assert observed.url.params["$top"] == "50"
    selected_fields = observed.url.params["$select"].split(",")
    assert "bodyPreview" in selected_fields
    assert "body" not in selected_fields
    assert observed.url.params["$filter"] == "isRead eq false"
    await http.aclose()


@pytest.mark.asyncio
async def test_send_mail_uses_graph_contract() -> None:
    bodies: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        import json

        bodies.append(json.loads(request.content))
        return httpx.Response(202)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    graph = MicrosoftGraphClient(StaticTokenProvider(), http_client=http)
    await graph.send_message(to=["a@example.com"], subject="Subject", body="Body")

    assert bodies[0]["message"]["toRecipients"][0]["emailAddress"]["address"] == "a@example.com"  # type: ignore[index]
    await http.aclose()
