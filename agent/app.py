"""FastAPI application factory and endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request

from agent import __version__
from agent.config import Settings, get_settings
from agent.dependencies import Container, build_container
from agent.exceptions import AgentError
from agent.logging import configure_logging
from agent.models.tools import ExecutionContext, ToolCall
from agent.schemas.api import (
    AuthenticationResponse,
    ChatRequest,
    ChatResponse,
    DeviceCodeResponse,
    HealthResponse,
    ToolExecutionRequest,
)


def create_app(
    settings: Settings | None = None,
    container: Container | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await container.close()

    app = FastAPI(
        title="MoMo AI Assistant",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.container = container

    @app.exception_handler(AgentError)
    async def agent_error_handler(_: Request, exc: AgentError) -> object:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=400,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version=__version__,
            microsoft_auth_configured=container.authenticator is not None,
            llm_configured=settings.llm_configured,
        )

    @app.get("/tools")
    async def tools() -> list[dict[str, object]]:
        return container.dispatcher.manifests()

    @app.post("/tool")
    async def execute_tool(payload: ToolExecutionRequest) -> object:
        context = ExecutionContext()
        call = ToolCall(
            tool=payload.tool,
            action=payload.action,
            parameters=payload.parameters,
            approval_status=payload.approval_status,
        )
        return await container.dispatcher.dispatch(call, context)

    @app.post("/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest) -> ChatResponse:
        context = ExecutionContext()
        outcome = await container.chat_service.chat(payload.message, payload.history, context)
        return ChatResponse(
            message=outcome.message,
            correlation_id=context.correlation_id,
            tool_results=outcome.tool_results,
        )

    @app.post("/auth/device-code", response_model=DeviceCodeResponse)
    async def start_device_code() -> DeviceCodeResponse:
        if container.authenticator is None:
            raise HTTPException(
                status_code=503,
                detail="Microsoft authentication is not configured.",
            )
        code = await container.authenticator.start_device_login()
        return DeviceCodeResponse(
            flow_id=code.flow_id,
            user_code=code.user_code,
            verification_uri=code.verification_uri,
            message=code.message,
            expires_in=code.expires_in,
        )

    @app.post("/auth/device-code/{flow_id}/complete", response_model=AuthenticationResponse)
    async def complete_device_code(flow_id: UUID) -> AuthenticationResponse:
        if container.authenticator is None:
            raise HTTPException(
                status_code=503,
                detail="Microsoft authentication is not configured.",
            )
        account = await container.authenticator.complete_device_login(flow_id)
        return AuthenticationResponse(authenticated=True, account=account.username)

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("agent.app:app", host="127.0.0.1", port=8000, reload=False)
