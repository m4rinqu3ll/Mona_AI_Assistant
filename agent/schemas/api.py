"""HTTP request and response schemas."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from agent.models.tools import ApprovalStatus, ToolResult


class ToolExecutionRequest(BaseModel):
    tool: str
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=30)


class ChatResponse(BaseModel):
    message: str
    correlation_id: UUID
    tool_results: list[ToolResult] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    microsoft_auth_configured: bool
    llm_configured: bool


class DeviceCodeResponse(BaseModel):
    flow_id: UUID
    user_code: str
    verification_uri: str
    message: str
    expires_in: int


class AuthenticationResponse(BaseModel):
    authenticated: bool
    account: str | None = None

