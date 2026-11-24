"""The configured reasoning effort must reach catalog-unknown gateway models.

Upstream only attaches an effort to models its catalog knows support reasoning,
so our opaque gateway aliases got nothing and scans hung in recon. The fork sends
the configured effort to catalog-unknown models by default
(``STRIX_FORCE_REASONING_FOR_UNKNOWN``), without touching known models.
"""

from __future__ import annotations

import strix.jitera.reasoning as reasoning
from strix.jitera.bootstrap import ENV_DEFAULTS


def test_disabled_never_forces() -> None:
    assert reasoning.force_for_unknown_model("gateway/alias", "high", enabled=False) is False


def test_unknown_model_forces_configured_effort(monkeypatch) -> None:
    monkeypatch.setattr("strix.config.models._catalog_entry", lambda _n: None)
    assert reasoning.force_for_unknown_model("dealignai/GLM-x", "high", enabled=True) is True


def test_known_model_not_forced(monkeypatch) -> None:
    # catalog knows the model -> leave upstream gating untouched
    monkeypatch.setattr("strix.config.models._catalog_entry", lambda _n: {"supports_reasoning": False})
    assert reasoning.force_for_unknown_model("gpt-known", "high", enabled=True) is False


def test_none_or_empty_effort_not_forced(monkeypatch) -> None:
    monkeypatch.setattr("strix.config.models._catalog_entry", lambda _n: None)
    assert reasoning.force_for_unknown_model("gw", "none", enabled=True) is False
    assert reasoning.force_for_unknown_model("gw", "", enabled=True) is False


def test_bad_effort_not_forced(monkeypatch) -> None:
    monkeypatch.setattr("strix.config.models._catalog_entry", lambda _n: None)
    assert reasoning.force_for_unknown_model("gw", "turbo", enabled=True) is False


def test_catalog_lookup_failure_is_safe(monkeypatch) -> None:
    def boom(_n):
        raise RuntimeError("catalog unavailable")

    monkeypatch.setattr("strix.config.models._catalog_entry", boom)
    assert reasoning.force_for_unknown_model("gw", "high", enabled=True) is False


def test_fork_enables_it_by_default() -> None:
    assert ENV_DEFAULTS.get("STRIX_FORCE_REASONING_FOR_UNKNOWN") == "true"


def test_upstream_setting_default_is_off() -> None:
    # the setting itself defaults off; only the fork's ENV_DEFAULTS turns it on
    from strix.config.settings import LlmSettings

    fields = LlmSettings.model_fields
    assert fields["force_reasoning_for_unknown"].default is False
