"""Tool dispatch contracts shared by API, dispatcher, and LLM layers."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ApprovalStatus(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ExecutionContext(BaseModel):
    correlation_id: UUID = Field(default_factory=uuid4)
    user_id: str | None = None


class ToolCall(BaseModel):
    tool: str = Field(min_length=1, max_length=80)
    action: str = Field(min_length=1, max_length=80)
    parameters: dict[str, Any] = Field(default_factory=dict)
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED


class ToolError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    success: bool
    tool: str
    action: str
    correlation_id: UUID
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    data: Any | None = None
    error: ToolError | None = None
    elapsed_ms: float = 0.0

