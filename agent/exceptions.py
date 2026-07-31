"""Structured application exceptions."""

from __future__ import annotations

from typing import Any


class AgentError(Exception):
    """Base exception safe to expose through the API."""

    code = "agent_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(AgentError):
    code = "configuration_error"


class AuthenticationRequiredError(AgentError):
    code = "authentication_required"


class AuthenticationError(AgentError):
    code = "authentication_error"


class ExternalServiceError(AgentError):
    code = "external_service_error"


class ToolNotFoundError(AgentError):
    code = "tool_not_found"


class ToolActionNotFoundError(AgentError):
    code = "tool_action_not_found"


class ToolValidationError(AgentError):
    code = "tool_validation_error"


class ToolExecutionError(AgentError):
    code = "tool_execution_error"

