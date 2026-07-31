"""Common contract implemented by every external connector tool."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, ClassVar

from pydantic import BaseModel, ValidationError

from agent.exceptions import ToolActionNotFoundError, ToolValidationError
from agent.models.tools import ExecutionContext


class EmptyParameters(BaseModel):
    pass


class BaseTool(ABC):
    """Validates action parameters and delegates only tool-specific business logic."""

    name: ClassVar[str]
    description: ClassVar[str]
    action_schemas: ClassVar[Mapping[str, type[BaseModel]]] = MappingProxyType({})
    mutating_actions: ClassVar[frozenset[str]] = frozenset()

    async def execute(
        self,
        action: str,
        parameters: dict[str, Any],
        context: ExecutionContext,
    ) -> Any:
        schema = self.action_schemas.get(action)
        if schema is None:
            raise ToolActionNotFoundError(
                f"Action '{action}' is not supported by tool '{self.name}'.",
                details={"available_actions": sorted(self.action_schemas)},
            )
        try:
            validated = schema.model_validate(parameters)
        except ValidationError as exc:
            raise ToolValidationError(
                f"Invalid parameters for {self.name}.{action}.",
                details={"validation_errors": exc.errors(include_url=False)},
            ) from exc
        return await self._execute(action, validated, context)

    def requires_approval(self, action: str) -> bool:
        return action in self.mutating_actions

    def manifest(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "actions": {
                action: {
                    "parameters": schema.model_json_schema(),
                    "requires_approval": self.requires_approval(action),
                }
                for action, schema in self.action_schemas.items()
            },
        }

    @abstractmethod
    async def _execute(
        self,
        action: str,
        parameters: BaseModel,
        context: ExecutionContext,
    ) -> Any:
        raise NotImplementedError
