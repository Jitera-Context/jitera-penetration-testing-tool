"""The edited upstream code follows the active brand profile.

Each check runs in a fresh interpreter so module-level values are computed under
the profile we choose, the way the ``jitera-pentest`` command runs, without touching
this test process.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from strix.jitera import brand


if TYPE_CHECKING:
    from pathlib import Path


def _evaluate(profile: str, expression: str) -> object:
    code = (
        "import json\n"
        "from strix.jitera import brand\n"
        f"brand.activate(brand.{profile})\n"
        f"print(json.dumps({expression}))\n"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def _module(name: str) -> str:
    return f"__import__({name!r}, fromlist=['x'])"


@pytest.mark.parametrize("profile", ["UPSTREAM", "JITERA"])
def test_sarif_tool_identity_follows_brand(profile: str) -> None:
    got = _evaluate(profile, f"{_module('strix.report.sarif')}.TOOL_NAME")
    assert got == getattr(brand, profile).name


@pytest.mark.parametrize("profile", ["UPSTREAM", "JITERA"])
def test_llm_attribution_follows_brand(profile: str) -> None:
    expected = getattr(brand, profile)
    got = _evaluate(profile, f"{_module('strix.config.models')}.APP_ATTRIBUTION_HEADERS")
    assert got == {"HTTP-Referer": expected.homepage, "X-Title": expected.name}


def _proxy_request(profile: str) -> str:
    raw = _evaluate(
        profile,
        f"{_module('strix.tools.proxy.caido_api')}.build_raw_request("
        "method='GET', url='https://example.com/', headers={}, body='')[1].decode()",
    )
    assert isinstance(raw, str)
    return raw


def test_proxy_replays_identify_jitera() -> None:
    assert "User-Agent: Mozilla/5.0 (compatible; Jitera/" in _proxy_request("JITERA")


def test_proxy_replays_keep_upstream_user_agent_for_upstream() -> None:
    assert "Chrome/125.0.0.0" in _proxy_request("UPSTREAM")


def test_explicit_user_agent_is_never_replaced() -> None:
    raw = _evaluate(
        "JITERA",
        f"{_module('strix.tools.proxy.caido_api')}.build_raw_request("
        "method='GET', url='https://example.com/', headers={'User-Agent': 'custom'}, "
        "body='')[1].decode()",
    )
    assert isinstance(raw, str)
    assert "User-Agent: custom" in raw


def _prompt(profile: str) -> str:
    rendered = _evaluate(profile, f"{_module('strix.agents.prompt')}.render_system_prompt()")
    assert isinstance(rendered, str)
    assert rendered
    return rendered


def test_agent_prompt_tells_the_agent_to_send_the_jitera_user_agent() -> None:
    rendered = _prompt("JITERA")
    assert 'User-Agent "Mozilla/5.0 (compatible; Jitera/' in rendered
    assert "NEVER use any identifiable names/markers" not in rendered


def test_agent_prompt_is_unchanged_for_upstream() -> None:
    rendered = _prompt("UPSTREAM")
    assert (
        "- NEVER use any identifiable names/markers in HTTP requests, payloads, "
        "user-agents, or any inputs\n\nINTER-AGENT MESSAGES:"
    ) in rendered


def test_sign_in_page_shows_jitera() -> None:
    page = _evaluate("JITERA", f"{_module('strix.interface.auth_cli')}._render_callback_html()")
    assert isinstance(page, str)
    assert "Jitera" in page
    assert "Strix" not in page
    assert "strix.ai" not in page


def test_viewer_server_header_names_jitera() -> None:
    header = _evaluate(
        "JITERA",
        f"{_module('strix.interface.viewer.server')}._make_handler(None).server_version",
    )
    assert header == "JiteraViewer/1.0"


def test_cli_help_uses_the_jitera_command_without_upstream_cloud(tmp_path: Path) -> None:
    # A throwaway home: the command copies settings from ~/.strix on first run.
    result = subprocess.run(
        [sys.executable, "-m", "strix.jitera", "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        env={**os.environ, "HOME": str(tmp_path)},
    )
    assert "jitera-pentest --target https://example.com" in result.stdout
    assert "Strix Cloud" not in result.stdout
    assert "Jitera Multi-Agent" in result.stdout
    assert "strix cloud" not in result.stdout
    assert "jitera-pentest view [RUN]" in result.stdout
