"""Memory interface reserved for future persistence providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MemoryProvider(ABC):
    @abstractmethod
    async def get(self, namespace: str, key: str) -> Any | None:
        raise NotImplementedError

    @abstractmethod
    async def put(self, namespace: str, key: str, value: Any) -> None:
        raise NotImplementedError

