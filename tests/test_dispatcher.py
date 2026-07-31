from __future__ import annotations

import pytest

from agent.dispatcher import ToolDispatcher
from agent.models.tools import ApprovalStatus, ExecutionContext, ToolCall
from agent.tools.email import EmailTool
from tests.fakes import FakeGraphClient


@pytest.mark.asyncio
async def test_dispatches_read_action() -> None:
    graph = FakeGraphClient()
    dispatcher = ToolDispatcher()
    dispatcher.register(EmailTool(graph))  # type: ignore[arg-type]

    result = await dispatcher.dispatch(
        ToolCall(tool="email", action="get_unread", parameters={"limit": 3}),
        ExecutionContext(),
    )

    assert result.success is True
    assert result.data == [{"id": "one", "subject": "Hello"}]
    assert graph.calls == [("get_unread_messages", {"limit": 3})]


@pytest.mark.asyncio
async def test_mutating_action_requires_approval() -> None:
    graph = FakeGraphClient()
    dispatcher = ToolDispatcher(auto_approve=False)
    dispatcher.register(EmailTool(graph))  # type: ignore[arg-type]
    call = ToolCall(
        tool="email",
        action="send",
        parameters={"to": ["person@example.com"], "subject": "Hi", "body": "Hello"},
    )

    pending = await dispatcher.dispatch(call, ExecutionContext())
    approved = await dispatcher.dispatch(
        call.model_copy(update={"approval_status": ApprovalStatus.APPROVED}),
        ExecutionContext(),
    )

    assert pending.approval_status == ApprovalStatus.PENDING_APPROVAL
    assert graph.calls == [("send_message", {
        "to": ["person@example.com"],
        "subject": "Hi",
        "body": "Hello",
        "content_type": "Text",
        "save_to_sent_items": True,
    })]
    assert approved.success is True


@pytest.mark.asyncio
async def test_validation_failure_is_structured() -> None:
    dispatcher = ToolDispatcher()
    dispatcher.register(EmailTool(FakeGraphClient()))  # type: ignore[arg-type]

    result = await dispatcher.dispatch(
        ToolCall(tool="email", action="get_unread", parameters={"limit": 500}),
        ExecutionContext(),
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "tool_validation_error"

