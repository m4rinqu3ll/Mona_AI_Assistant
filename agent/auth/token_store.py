"""Secure token cache persistence abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from threading import RLock


class TokenStore(ABC):
    @abstractmethod
    def load(self) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, serialized_cache: str) -> None:
        raise NotImplementedError


class KeyringTokenStore(TokenStore):
    """Stores the MSAL cache in the operating system credential vault."""

    def __init__(self, service_name: str, account_name: str = "msal-token-cache") -> None:
        import keyring

        self._keyring = keyring
        self._service_name = service_name
        self._account_name = account_name
        self._lock = RLock()

    def load(self) -> str | None:
        with self._lock:
            return self._keyring.get_password(self._service_name, self._account_name)

    def save(self, serialized_cache: str) -> None:
        with self._lock:
            self._keyring.set_password(
                self._service_name,
                self._account_name,
                serialized_cache,
            )


class InMemoryTokenStore(TokenStore):
    """Non-persistent token store for tests and explicit ephemeral deployments."""

    def __init__(self) -> None:
        self.value: str | None = None

    def load(self) -> str | None:
        return self.value

    def save(self, serialized_cache: str) -> None:
        self.value = serialized_cache

