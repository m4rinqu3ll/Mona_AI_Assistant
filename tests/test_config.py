import pytest

from agent.config import Settings


def test_csv_scopes_are_parsed() -> None:
    settings = Settings(ms_scopes="User.Read, Mail.ReadWrite")  # type: ignore[arg-type]
    assert settings.ms_scopes == ["User.Read", "Mail.ReadWrite"]
    assert settings.ms_authority.endswith("/common")


def test_csv_scopes_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MS_SCOPES", "User.Read,Mail.ReadWrite,Mail.Send")
    assert Settings().ms_scopes == ["User.Read", "Mail.ReadWrite", "Mail.Send"]


def test_deepseek_configuration_requires_key() -> None:
    missing = Settings(llm_provider="deepseek")
    configured = Settings(llm_provider="deepseek", deepseek_api_key="test-key")
    assert missing.llm_configured is False
    assert configured.llm_configured is True
