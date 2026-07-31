from __future__ import annotations

import pytest

from agent.auth.token_store import KeyringTokenStore


class FakeKeyring:
    def __init__(self, *, max_password_length: int = 1_100) -> None:
        self.values: dict[tuple[str, str], str] = {}
        self.max_password_length = max_password_length

    def get_password(self, service_name: str, username: str) -> str | None:
        return self.values.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        if len(password) > self.max_password_length:
            raise OSError("credential is too large")
        self.values[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        self.values.pop((service_name, username), None)


def test_large_cache_is_chunked_and_round_trips() -> None:
    backend = FakeKeyring()
    store = KeyringTokenStore("mona-test", keyring_backend=backend)
    serialized_cache = '{"AccessToken":"' + ("token-data-" * 2_000) + '"}'

    store.save(serialized_cache)

    assert store.load() == serialized_cache
    assert len(backend.values) > 2
    assert all(len(value) <= 1_000 for value in backend.values.values())


def test_load_supports_legacy_single_entry() -> None:
    backend = FakeKeyring()
    backend.values[("mona-test", "msal-token-cache")] = "legacy-cache"
    store = KeyringTokenStore("mona-test", keyring_backend=backend)

    assert store.load() == "legacy-cache"


def test_replacing_cache_removes_previous_generation() -> None:
    backend = FakeKeyring()
    store = KeyringTokenStore("mona-test", keyring_backend=backend)
    store.save("first-cache" * 1_000)
    first_generation_accounts = {
        username
        for service, username in backend.values
        if service == "mona-test" and ":chunk:" in username
    }

    store.save("second-cache" * 1_000)

    current_generation_accounts = {
        username
        for service, username in backend.values
        if service == "mona-test" and ":chunk:" in username
    }
    assert store.load() == "second-cache" * 1_000
    assert first_generation_accounts.isdisjoint(current_generation_accounts)


def test_incomplete_cache_is_rejected() -> None:
    backend = FakeKeyring()
    store = KeyringTokenStore("mona-test", keyring_backend=backend)
    store.save("cache-data" * 1_000)
    chunk_key = next(key for key in backend.values if ":chunk:" in key[1])
    del backend.values[chunk_key]

    with pytest.raises(RuntimeError, match="incomplete"):
        store.load()
