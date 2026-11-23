"""The ``--reasoning-effort`` run parameter sends the model's effort, even for
models LiteLLM's catalog does not know (our gateway aliases)."""

from __future__ import annotations

import pytest

from strix.core.inputs import make_model_settings
from strix.interface.cli_args import parse_arguments
from strix.jitera import reasoning


# A model LiteLLM's cost map has no entry for: today's effort is dropped for it.
_UNLISTED = "openai/dealignai/GLM-5.3-Flash-UNCENSORED-FP8"


def test_resolve_without_the_parameter_keeps_the_setting_and_does_not_force() -> None:
    assert reasoning.resolve(None, "high") == ("high", False)
    assert reasoning.resolve(None, "none") == ("none", False)


def test_resolve_with_the_parameter_wins_and_forces() -> None:
    assert reasoning.resolve("low", "high") == ("low", True)
    assert reasoning.resolve("none", "high") == ("none", True)


def test_auto_resolves_to_the_maximum_level() -> None:
    assert reasoning.resolve("auto", "high") == ("max", True)
    assert reasoning.AUTO not in reasoning.LEVELS
    assert reasoning.LEVELS[-1] == "max"
    assert (*reasoning.LEVELS, "auto") == reasoning.CLI_CHOICES


def test_resolve_falls_back_on_an_unknown_or_empty_value_without_crashing() -> None:
    # A bad value never forces anything and never raises (guards non-CLI callers
    # of the runner); it uses the configured setting instead.
    assert reasoning.resolve("ludicrous", "high") == ("high", False)
    assert reasoning.resolve("", "high") == ("high", False)
    assert reasoning.resolve("   ", "medium") == ("medium", False)


def test_resolve_is_case_insensitive() -> None:
    assert reasoning.resolve("MAX", "high") == ("max", True)
    assert reasoning.resolve("Auto", "low") == ("max", True)


def test_unlisted_model_drops_the_effort_without_force() -> None:
    # The bug the parameter exists to fix: nothing is sent for our models today.
    settings = make_model_settings("high", model_name=_UNLISTED, force_reasoning=False)
    assert settings.reasoning is None
    assert (settings.extra_body or {}).get("reasoning_effort") is None


def test_force_sends_a_normal_level_as_reasoning_effort() -> None:
    settings = make_model_settings("high", model_name=_UNLISTED, force_reasoning=True)
    assert settings.reasoning is not None
    assert settings.reasoning.effort == "high"


def test_force_sends_max_as_a_raw_body_field() -> None:
    # ``max`` is not in the SDK's Reasoning enum, so it rides in extra_body.
    settings = make_model_settings("max", model_name=_UNLISTED, force_reasoning=True)
    assert (settings.extra_body or {}).get("reasoning_effort") == "max"


def test_force_never_sends_none() -> None:
    settings = make_model_settings("none", model_name=_UNLISTED, force_reasoning=True)
    assert settings.reasoning is None
    assert (settings.extra_body or {}).get("reasoning_effort") is None


def test_the_cli_arg_parses_and_defaults_to_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv", ["jitera-pentest", "-n", "--target", "http://x", "--reasoning-effort", "max"]
    )
    assert parse_arguments().reasoning_effort == "max"

    monkeypatch.setattr("sys.argv", ["jitera-pentest", "-n", "--target", "http://x"])
    assert parse_arguments().reasoning_effort is None

    # Case-insensitive, like the STRIX_REASONING_EFFORT env var.
    monkeypatch.setattr(
        "sys.argv", ["jitera-pentest", "-n", "--target", "http://x", "--reasoning-effort", "HIGH"]
    )
    assert parse_arguments().reasoning_effort == "high"


def test_the_cli_arg_rejects_an_unknown_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv", ["jitera-pentest", "-n", "--target", "http://x", "--reasoning-effort", "turbo"]
    )
    with pytest.raises(SystemExit):
        parse_arguments()


def test_runner_glue_from_scan_config_puts_max_on_the_request() -> None:
    # Mirrors strix/core/runner.py: resolve the scan_config value, then build the
    # settings. Locks the scan_config key name both builders write.
    scan_config = {"reasoning_effort": "auto"}
    effort, force = reasoning.resolve(scan_config.get("reasoning_effort"), "high")
    settings = make_model_settings(effort, model_name=_UNLISTED, force_reasoning=force)
    assert (settings.extra_body or {}).get("reasoning_effort") == "max"


def test_runner_glue_without_the_parameter_sends_nothing_for_an_unlisted_model() -> None:
    scan_config: dict[str, object] = {}
    effort, force = reasoning.resolve(scan_config.get("reasoning_effort"), "high")
    settings = make_model_settings(effort, model_name=_UNLISTED, force_reasoning=force)
    assert settings.reasoning is None
    assert (settings.extra_body or {}).get("reasoning_effort") is None
