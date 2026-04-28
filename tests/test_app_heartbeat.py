"""Heartbeat configuration and helper tests."""

import pytest

from config import load_settings
from pump_system.app import _format_uptime


def test_settings_default_heartbeat_is_enabled_with_900s_interval(monkeypatch) -> None:
    monkeypatch.delenv("HEARTBEAT_ENABLED", raising=False)
    monkeypatch.delenv("HEARTBEAT_INTERVAL_SECONDS", raising=False)

    settings = load_settings()

    assert settings.heartbeat_enabled is True
    assert settings.heartbeat_interval_seconds == 900


def test_settings_heartbeat_disabled(monkeypatch) -> None:
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")

    settings = load_settings()

    assert settings.heartbeat_enabled is False


def test_settings_heartbeat_custom_interval(monkeypatch) -> None:
    monkeypatch.setenv("HEARTBEAT_INTERVAL_SECONDS", "1800")

    settings = load_settings()

    assert settings.heartbeat_interval_seconds == 1800


def test_settings_rejects_heartbeat_interval_below_60s(monkeypatch) -> None:
    monkeypatch.setenv("HEARTBEAT_INTERVAL_SECONDS", "30")

    with pytest.raises(ValueError, match="HEARTBEAT_INTERVAL_SECONDS"):
        load_settings()


def test_format_uptime_below_one_hour() -> None:
    assert _format_uptime(0) == "00:00:00"
    assert _format_uptime(59) == "00:00:59"
    assert _format_uptime(60) == "00:01:00"
    assert _format_uptime(3599) == "00:59:59"


def test_format_uptime_multi_hour() -> None:
    assert _format_uptime(3600) == "01:00:00"
    assert _format_uptime(3661) == "01:01:01"
    assert _format_uptime(36000) == "10:00:00"


def test_format_uptime_clamps_negative() -> None:
    assert _format_uptime(-100) == "00:00:00"
