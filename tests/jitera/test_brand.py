from __future__ import annotations

from strix.jitera import brand


def test_upstream_profile_is_active_by_default() -> None:
    assert brand.current() is brand.UPSTREAM


def test_activate_switches_profile() -> None:
    brand.activate(brand.JITERA)
    assert brand.current().name == brand.JITERA.name


def test_user_agent_names_product_version_and_homepage() -> None:
    agent = brand.JITERA.user_agent("1.2.3")
    assert agent == f"{brand.JITERA.user_agent_token}/1.2.3 (+{brand.JITERA.homepage})"
    assert " " not in brand.JITERA.user_agent_token
