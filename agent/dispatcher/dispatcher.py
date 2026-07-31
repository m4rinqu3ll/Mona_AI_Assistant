"""Generic tool router with validation, approval, timing, and exception isolation."""

from __future__ import annotations

import logging
from typing import Any

from agent.exceptions import AgentError, ToolNotFoundError
from agent.logging import Timer, correlation_id_var
from agent.models.tools import (
    ApprovalStatus,
    ExecutionContext,
    ToolCall,
    ToolError,
    ToolResult,
)
from agent.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolDispatcher:
    def __init__(self, *, auto_approve: bool = False) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._auto_approve = auto_approve

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def manifests(self) -> list[dict[str, Any]]:
        return [self._tools[name].manifest() for name in sorted(self._tools)]

    async def dispatch(self, call: ToolCall, context: ExecutionContext) -> ToolResult:
        token = correlation_id_var.set(str(context.correlation_id))
        timer = Timer()
        try:
            with timer:
                tool = self._tools.get(call.tool)
                if tool is None:
                    raise ToolNotFoundError(
                        f"Tool '{call.tool}' is not registered.",
                        details={"available_tools": sorted(self._tools)},
                    )
                if tool.requires_approval(call.action):
                    if call.approval_status == ApprovalStatus.REJECTED:
                        return self._pending_result(
                            call,
                            context,
                            timer,
                            ApprovalStatus.REJECTED,
                        )
                    if not self._auto_approve and call.approval_status != ApprovalStatus.APPROVED:
                        return self._pending_result(
                            call,
                            context,
                            timer,
                            ApprovalStatus.PENDING_APPROVAL,
                        )
                data = await tool.execute(call.action, call.parameters, context)
            logger.info(
                "Tool executed",
                extra={
                    "tool_name": call.tool,
                    "action": call.action,
                    "elapsed_ms": round(timer.elapsed_ms, 3),
                },
            )
            return ToolResult(
                success=True,
                tool=call.tool,
                action=call.action,
                correlation_id=context.correlation_id,
                approval_status=(
                    ApprovalStatus.APPROVED
                    if tool.requires_approval(call.action)
                    else ApprovalStatus.NOT_REQUIRED
                ),
                data=data,
                elapsed_ms=timer.elapsed_ms,
            )
        except AgentError as exc:
            logger.warning(
                "Tool execution failed",
                extra={
                    "tool_name": call.tool,
                    "action": call.action,
                    "elapsed_ms": round(timer.elapsed_ms, 3),
                    "error_code": exc.code,
                },
            )
            return self._error_result(call, context, timer, exc.code, exc.message, exc.details)
        except Exception:
            logger.exception(
                "Unexpected tool failure",
                extra={
                    "tool_name": call.tool,
                    "action": call.action,
                    "elapsed_ms": round(timer.elapsed_ms, 3),
                    "error_code": "internal_tool_error",
                },
            )
            return self._error_result(
                call,
                context,
                timer,
                "internal_tool_error",
                "The tool failed unexpectedly.",
                {},
            )
        finally:
            correlation_id_var.reset(token)

    @staticmethod
    def _pending_result(
        call: ToolCall,
        context: ExecutionContext,
        timer: Timer,
        status: ApprovalStatus,
    ) -> ToolResult:
        return ToolResult(
            success=False,
            tool=call.tool,
            action=call.action,
            correlation_id=context.correlation_id,
            approval_status=status,
            data={"parameters": call.parameters},
            elapsed_ms=timer.elapsed_ms,
        )

    @staticmethod
    def _error_result(
        call: ToolCall,
        context: ExecutionContext,
        timer: Timer,
        code: str,
        message: str,
        details: dict[str, Any],
    ) -> ToolResult:
        return ToolResult(
            success=False,
            tool=call.tool,
            action=call.action,
            correlation_id=context.correlation_id,
            error=ToolError(code=code, message=message, details=details),
            elapsed_ms=timer.elapsed_ms,
        )

