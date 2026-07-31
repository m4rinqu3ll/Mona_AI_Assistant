"""Microsoft Entra ID OAuth using MSAL device-code flow."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from agent.auth.token_store import TokenStore
from agent.exceptions import AuthenticationError, AuthenticationRequiredError


class TokenProvider(Protocol):
    async def get_access_token(self) -> str:
        """Return a currently valid access token or raise an authentication error."""


@dataclass(frozen=True, slots=True)
class DeviceCode:
    flow_id: UUID
    user_code: str
    verification_uri: str
    message: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class AuthenticatedAccount:
    username: str | None


class MicrosoftAuthenticator(TokenProvider):
    """Manages OAuth tokens without handling or storing user passwords."""

    def __init__(
        self,
        *,
        client_id: str,
        authority: str,
        scopes: list[str],
        token_store: TokenStore,
        application: Any | None = None,
    ) -> None:
        if not client_id:
            raise ValueError("client_id is required")
        if application is None:
            import msal  # type: ignore[import-untyped]

            self._cache = msal.SerializableTokenCache()
            serialized = token_store.load()
            if serialized:
                self._cache.deserialize(serialized)
            application = msal.PublicClientApplication(
                client_id=client_id,
                authority=authority,
                token_cache=self._cache,
            )
        else:
            self._cache = getattr(application, "token_cache", None)
        self._application = application
        self._scopes = scopes
        self._token_store = token_store
        self._pending_flows: dict[UUID, dict[str, Any]] = {}

    async def get_access_token(self) -> str:
        accounts = await asyncio.to_thread(self._application.get_accounts)
        result: dict[str, Any] | None = None
        if accounts:
            result = await asyncio.to_thread(
                self._application.acquire_token_silent,
                self._scopes,
                account=accounts[0],
            )
        self._persist_cache()
        if result and result.get("access_token"):
            return str(result["access_token"])
        raise AuthenticationRequiredError(
            "Microsoft authentication is required. Start the device-code login flow."
        )

    async def start_device_login(self) -> DeviceCode:
        flow = await asyncio.to_thread(
            self._application.initiate_device_flow,
            scopes=self._scopes,
        )
        if "user_code" not in flow:
            raise AuthenticationError(
                "Microsoft did not return a device code.",
                details={"error": flow.get("error"), "description": flow.get("error_description")},
            )
        flow_id = uuid4()
        self._pending_flows[flow_id] = flow
        return DeviceCode(
            flow_id=flow_id,
            user_code=str(flow["user_code"]),
            verification_uri=str(flow.get("verification_uri") or flow.get("verification_url")),
            message=str(flow.get("message", "Complete sign-in in your browser.")),
            expires_in=int(flow.get("expires_in", 900)),
        )

    async def complete_device_login(self, flow_id: UUID) -> AuthenticatedAccount:
        flow = self._pending_flows.pop(flow_id, None)
        if flow is None:
            raise AuthenticationError("The device-code flow is unknown or has expired.")
        result = await asyncio.to_thread(self._application.acquire_token_by_device_flow, flow)
        self._persist_cache()
        if "access_token" not in result:
            raise AuthenticationError(
                "Microsoft authentication failed.",
                details={
                    "error": result.get("error"),
                    "description": result.get("error_description"),
                },
            )
        claims = result.get("id_token_claims") or {}
        return AuthenticatedAccount(username=claims.get("preferred_username"))

    def _persist_cache(self) -> None:
        if self._cache is not None and getattr(self._cache, "has_state_changed", False):
            self._token_store.save(self._cache.serialize())
