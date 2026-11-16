"""Brand values: the only place product names, links and User-Agent text live.

Upstream files read the active profile through ``current()``. The profile is
``UPSTREAM`` unless the ``jitera`` command activates ``JITERA``, so upstream's
own tests keep seeing the Strix values.

This module imports nothing from ``strix`` so it can be activated before any
upstream module loads.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Brand:
    name: str  # product name shown to people
    command: str  # CLI command
    homepage: str
    docs_url: str
    release_repo: str  # GitHub owner/repo that publishes releases

    @property
    def user_agent_token(self) -> str:
        return self.name.replace(" ", "")

    def user_agent(self, version: str) -> str:
        return f"{self.user_agent_token}/{version} (+{self.homepage})"


UPSTREAM = Brand(
    name="Strix",
    command="strix",
    homepage="https://strix.ai",
    docs_url="https://docs.strix.ai",
    release_repo="usestrix/strix",
)

# Placeholder values until the brand decision is final. Change them here only.
JITERA = Brand(
    name="Jitera Pentest",
    command="jitera",
    homepage="https://jitera.com",
    docs_url="https://jitera.com",
    release_repo="Jitera-Context/jitera-penetration-testing-tool",
)

_state: dict[str, Brand] = {"active": UPSTREAM}


def activate(profile: Brand) -> None:
    _state["active"] = profile


def current() -> Brand:
    return _state["active"]
