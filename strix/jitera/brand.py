"""Brand values: the only place product names, links and User-Agent text live.

Upstream files read the active profile through ``current()``. The profile is
``UPSTREAM`` unless the ``jitera`` command activates ``JITERA``, so upstream's
own tests keep seeing the Strix values.

This module imports nothing from ``strix`` so it can be activated before any
upstream module loads.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from urllib.parse import urlparse


@dataclass(frozen=True)
class Brand:
    name: str  # product name shown to people
    command: str  # CLI command
    homepage: str
    docs_url: str
    release_repo: str  # GitHub owner/repo that publishes releases
    tagline: str
    links: tuple[str, ...]  # shown under the CLI's end-of-scan panel
    promo: tuple[tuple[str, str], ...]  # (label, url) upsell lines; empty hides them
    identify_scan_traffic: bool  # send our User-Agent to scan targets too

    @property
    def user_agent_token(self) -> str:
        return self.name.replace(" ", "")

    def user_agent(self, version: str | None = None) -> str:
        """User-Agent for the tool's own calls (LLM gateways, GitHub, search APIs)."""
        return f"{self.user_agent_token}/{version or package_version()} (+{self.homepage})"

    def scan_user_agent(self, default: str) -> str:
        """User-Agent for requests sent to scan targets.

        Browser-compatible so targets render normally, and named so the client
        can identify and allowlist our authorized traffic. ``default`` is the
        upstream value, kept when this profile does not identify scan traffic.
        """
        if not self.identify_scan_traffic:
            return default
        token = f"{self.user_agent_token}/{package_version()}"
        return f"Mozilla/5.0 (compatible; {token}; +{self.homepage})"

    def sandbox_env(self) -> dict[str, str]:
        """Environment for the sandbox container: its browser's User-Agent."""
        if not self.identify_scan_traffic:
            return {}
        return {"AGENT_BROWSER_USER_AGENT": self.scan_user_agent("")}


def package_version() -> str:
    try:
        return version("strix-agent")
    except PackageNotFoundError:
        return "dev"


UPSTREAM = Brand(
    name="Strix",
    command="strix",
    homepage="https://strix.ai",
    docs_url="https://docs.strix.ai",
    release_repo="usestrix/strix",
    tagline="Open-source AI hackers for your apps",
    links=("strix.ai", "docs.strix.ai", "discord.gg/strix-ai"),
    promo=(("Run a pentest in Strix Cloud", "app.strix.ai"), ("Enterprise", "strix.ai/demo")),
    identify_scan_traffic=False,
)

JITERA = Brand(
    name="Jitera",
    command="jitera",
    homepage="https://jitera.com",
    docs_url="https://jitera.com",
    release_repo="Jitera-Context/jitera-penetration-testing-tool",
    tagline="AI hackers for your apps",
    links=("jitera.com",),
    promo=(),
    identify_scan_traffic=True,
)

_state: dict[str, Brand] = {"active": UPSTREAM}


def activate(profile: Brand) -> None:
    _state["active"] = profile


def current() -> Brand:
    return _state["active"]


def rebrand(text: str) -> str:
    """Rewrite upstream product mentions in a block of upstream-written text.

    For pages and help blocks where editing every line would make a large
    patch. Returns the text unchanged under the upstream profile.
    """
    profile = current()
    if profile is UPSTREAM:
        return text
    for old, new in (
        ("https://docs.strix.ai", profile.docs_url),
        ("https://discord.gg/strix-ai", profile.homepage),
        ("https://strix.ai", profile.homepage),
        ("strix.ai", urlparse(profile.homepage).netloc),
        ("Strix", profile.name),
    ):
        text = text.replace(old, new)
    return text


def rebrand_commands(text: str) -> str:
    """Point upstream's ``strix <subcommand>`` help lines at our command.

    Lines for Strix Cloud are dropped when the profile has no upstream promo,
    because the ``jitera`` command blocks ``cloud``.
    """
    profile = current()
    if profile is UPSTREAM:
        return text
    lines = [
        line.replace("strix ", f"{profile.command} ")
        for line in text.splitlines()
        if profile.promo or "strix cloud" not in line
    ]
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
