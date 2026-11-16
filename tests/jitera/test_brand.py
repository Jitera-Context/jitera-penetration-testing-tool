from __future__ import annotations

from strix.jitera import bootstrap, brand


def test_upstream_profile_is_active_by_default() -> None:
    assert brand.current() is brand.UPSTREAM


def test_activate_switches_profile() -> None:
    brand.activate(brand.JITERA)
    assert brand.current().name == "Jitera"


def test_tool_user_agent_names_jitera() -> None:
    assert brand.JITERA.user_agent("1.2.3") == "Jitera/1.2.3 (+https://jitera.com)"


def test_scan_user_agent_identifies_jitera_and_stays_browser_compatible() -> None:
    agent = brand.JITERA.scan_user_agent("upstream default")
    assert agent.startswith("Mozilla/5.0 (compatible; Jitera/")
    assert agent.endswith("; +https://jitera.com)")


def test_upstream_profile_keeps_upstream_scan_user_agent() -> None:
    assert brand.UPSTREAM.scan_user_agent("upstream default") == "upstream default"
    assert brand.UPSTREAM.sandbox_env() == {}


def test_sandbox_browser_gets_the_scan_user_agent() -> None:
    env = brand.JITERA.sandbox_env()
    assert env == {"AGENT_BROWSER_USER_AGENT": brand.JITERA.scan_user_agent("")}


def test_rebrand_is_a_no_op_for_upstream() -> None:
    text = "Strix at https://strix.ai, docs at https://docs.strix.ai"
    assert brand.rebrand(text) == text


def test_rebrand_rewrites_upstream_mentions_for_jitera() -> None:
    brand.activate(brand.JITERA)
    text = "Strix at https://strix.ai · strix.ai · https://docs.strix.ai"
    assert brand.rebrand(text) == "Jitera at https://jitera.com · jitera.com · https://jitera.com"


def test_terminal_ui_receives_the_brand() -> None:
    assert bootstrap.brand_environment(brand.JITERA) == {
        "STRIX_BRAND_NAME": "Jitera",
        "STRIX_BRAND_URL": "jitera.com",
        "STRIX_BRAND_TAGLINE": brand.JITERA.tagline,
    }


def test_subcommand_help_points_at_our_command_without_cloud() -> None:
    text = "Additional commands:\n  strix cloud ...  Cloud\n  strix view [RUN]  View\n"
    assert brand.rebrand_commands(text) == text
    brand.activate(brand.JITERA)
    assert brand.rebrand_commands(text) == "Additional commands:\n  jitera view [RUN]  View\n"
