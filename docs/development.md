# Development guide

## Local workflow

Use Python 3.12 and install the locked development environment with uv:

```powershell
uv sync --extra dev
uv run ruff check .
uv run mypy agent
uv run pytest
```

Keep external clients dependency-injectable. Tests should use fakes or `httpx.MockTransport`; they
must not require a live mailbox or model API.

## Configuration

All settings are defined in `agent/config.py` and load from environment variables or a local
`.env`. Add documented placeholders to `.env.example`, never real values. Production deployments
should inject settings from their secret manager instead of shipping a `.env` file.

## Logging and errors

Raise an `AgentError` subtype for failures callers can act on. The dispatcher converts these into
structured `ToolResult.error` values and sanitizes unexpected exceptions. Never log OAuth tokens,
message bodies, API keys, or raw credential-cache data.

## Testing a new tool

Cover parameter validation, every supported action, approval classification for mutations,
external client failures, and the manifest. Also add one dispatcher test to prove the new tool is
registered through dependency composition.
