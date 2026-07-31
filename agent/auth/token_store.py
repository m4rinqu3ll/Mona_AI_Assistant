"""Secure token cache persistence abstractions."""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from threading import RLock
from typing import Protocol, cast
from uuid import uuid4


class KeyringBackend(Protocol):
    def get_password(self, service_name: str, username: str) -> str | None: ...

    def set_password(self, service_name: str, username: str, password: str) -> None: ...

    def delete_password(self, service_name: str, username: str) -> None: ...


class TokenStore(ABC):
    @abstractmethod
    def load(self) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, serialized_cache: str) -> None:
        raise NotImplementedError


class KeyringTokenStore(TokenStore):
    """Stores the MSAL cache in safe-sized chunks in the OS credential vault.

    Windows Credential Manager limits a single credential blob to 2,560 bytes and
    keyring stores strings as UTF-16. An MSAL cache commonly exceeds that limit, so
    each generation is base64 encoded and split across multiple vault entries. The
    small manifest is written last, making a new generation visible atomically.
    """

    _MANIFEST_PREFIX = "mona-keyring-chunks-v1:"
    _CHUNK_SIZE = 1_000
    _MAX_CHUNKS = 10_000

    def __init__(
        self,
        service_name: str,
        account_name: str = "msal-token-cache",
        *,
        keyring_backend: KeyringBackend | None = None,
    ) -> None:
        if keyring_backend is None:
            import keyring

            keyring_backend = cast(KeyringBackend, keyring)

        self._keyring = keyring_backend
        self._service_name = service_name
        self._account_name = account_name
        self._lock = RLock()

    def load(self) -> str | None:
        with self._lock:
            stored = self._keyring.get_password(self._service_name, self._account_name)
            if stored is None:
                return None

            manifest = self._parse_manifest(stored)
            if manifest is None:
                # Backward compatibility with the original single-entry store.
                return stored

            generation, chunk_count = manifest
            chunks: list[str] = []
            for index in range(chunk_count):
                chunk = self._keyring.get_password(
                    self._service_name,
                    self._chunk_account_name(generation, index),
                )
                if chunk is None:
                    raise RuntimeError("The secure Microsoft token cache is incomplete.")
                chunks.append(chunk)

            try:
                return base64.b64decode("".join(chunks), validate=True).decode("utf-8")
            except (ValueError, UnicodeDecodeError) as exc:
                raise RuntimeError("The secure Microsoft token cache is corrupted.") from exc

    def save(self, serialized_cache: str) -> None:
        with self._lock:
            current = self._keyring.get_password(self._service_name, self._account_name)
            previous_manifest = self._parse_manifest(current) if current is not None else None

            encoded = base64.b64encode(serialized_cache.encode("utf-8")).decode("ascii")
            chunks = [
                encoded[start : start + self._CHUNK_SIZE]
                for start in range(0, len(encoded), self._CHUNK_SIZE)
            ] or [""]
            generation = uuid4().hex

            try:
                for index, chunk in enumerate(chunks):
                    self._keyring.set_password(
                        self._service_name,
                        self._chunk_account_name(generation, index),
                        chunk,
                    )
                self._keyring.set_password(
                    self._service_name,
                    self._account_name,
                    f"{self._MANIFEST_PREFIX}{generation}:{len(chunks)}",
                )
            except Exception:
                self._delete_generation(generation, len(chunks))
                raise

            if previous_manifest is not None:
                previous_generation, previous_chunk_count = previous_manifest
                self._delete_generation(previous_generation, previous_chunk_count)

    def _parse_manifest(self, stored: str) -> tuple[str, int] | None:
        if not stored.startswith(self._MANIFEST_PREFIX):
            return None

        payload = stored.removeprefix(self._MANIFEST_PREFIX)
        try:
            generation, chunk_count_text = payload.split(":", maxsplit=1)
            chunk_count = int(chunk_count_text)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("The secure Microsoft token cache manifest is invalid.") from exc

        is_hex_generation = len(generation) == 32 and all(
            character in "0123456789abcdef" for character in generation
        )
        if not is_hex_generation or not 1 <= chunk_count <= self._MAX_CHUNKS:
            raise RuntimeError("The secure Microsoft token cache manifest is invalid.")
        return generation, chunk_count

    def _chunk_account_name(self, generation: str, index: int) -> str:
        return f"{self._account_name}:chunk:{generation}:{index:05d}"

    def _delete_generation(self, generation: str, chunk_count: int) -> None:
        for index in range(chunk_count):
            try:
                self._keyring.delete_password(
                    self._service_name,
                    self._chunk_account_name(generation, index),
                )
            except Exception:
                # Cleanup is best effort. The manifest never points at this generation
                # after a failed write or a successful replacement.
                continue


class InMemoryTokenStore(TokenStore):
    """Non-persistent token store for tests and explicit ephemeral deployments."""

    def __init__(self) -> None:
        self.value: str | None = None

    def load(self) -> str | None:
        return self.value

    def save(self, serialized_cache: str) -> None:
        self.value = serialized_cache
