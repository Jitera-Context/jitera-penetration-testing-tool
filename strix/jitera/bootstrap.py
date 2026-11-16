"""Entry point of the ``jitera-pentest`` command.

Order matters: activate the Jitera brand and environment defaults first, then
register our tools and skills with upstream's hooks, then hand over to the
unchanged Strix CLI.

Imports inside functions are deliberate: the brand must be active before any
``strix`` module loads, because upstream modules read it at import time.
"""

# ruff: noqa: PLC0415

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from strix.jitera import brand, dotenv


if TYPE_CHECKING:
    from collections.abc import MutableMapping, Sequence


SKILLS_DIR = Path(__file__).resolve().parent / "skills"

# Defaults for settings upstream already reads. An explicit value always wins.
ENV_DEFAULTS: dict[str, str] = {
    "STRIX_TELEMETRY": "0",  # no usage data to the upstream vendor
    "STRIX_NO_UPDATE_CHECK": "1",  # until our own release channel exists
}

# Upstream features that lead to the upstream vendor's services.
BLOCKED: dict[str, str] = {
    "cloud": "Strix Cloud is the upstream vendor's paid platform.",
    "--update": "Self-update would install upstream Strix. Reinstall from our releases instead.",
}


def brand_environment(profile: brand.Brand) -> dict[str, str]:
    """Brand values for the Go terminal UI, which inherits this environment."""
    return {
        "STRIX_BRAND_NAME": profile.name,
        "STRIX_BRAND_URL": urlparse(profile.homepage).netloc or profile.homepage,
        "STRIX_BRAND_TAGLINE": profile.tagline,
    }


def prepare_environment(env: MutableMapping[str, str], profile: brand.Brand | None = None) -> None:
    """Copy our prefixed settings (JITERA_PENTEST_*) to STRIX_* and apply our defaults.

    Only our own prefix is copied, never a bare JITERA_*, which other Jitera
    tools such as the Jitera Gateway use.
    """
    profile = profile or brand.current()
    if profile.env_prefix != "STRIX_":
        for key in [k for k in env if k.startswith(profile.env_prefix)]:
            env.setdefault("STRIX_" + key.removeprefix(profile.env_prefix), env[key])
    for key, value in {**ENV_DEFAULTS, **brand_environment(profile)}.items():
        env.setdefault(key, value)


def blocked_reason(argv: Sequence[str]) -> str | None:
    if argv and argv[0] in BLOCKED:
        return BLOCKED[argv[0]]
    if "--update" in argv:
        return BLOCKED["--update"]
    return None


def install_user_agent() -> None:
    """Name our product on host-side HTTP calls made with ``requests``.

    Requests to scan targets set their own neutral browser User-Agent
    explicitly, so this default never reaches them.
    """
    import requests.utils

    agent = brand.current().user_agent()

    def _user_agent(name: str = "python-requests") -> str:  # noqa: ARG001
        return agent

    requests.utils.default_user_agent = _user_agent


def register_extensions() -> None:
    """Hand our tools and skills to upstream's registration hooks."""
    from strix.agents.factory import register_agent_tools
    from strix.jitera.tools import get_tools
    from strix.skills import register_skill_dir

    register_skill_dir(SKILLS_DIR)
    tools = get_tools()
    if tools:
        register_agent_tools(*tools)


def load_env_file() -> None:
    """Read our .env (see strix/jitera/dotenv.py). The real environment wins."""
    path = dotenv.default_env_file()
    if os.environ.get(dotenv.ENV_FILE_VAR) and not path.is_file():
        sys.stderr.write(f"{dotenv.ENV_FILE_VAR} points to a missing file: {path}\n")
    dotenv.load(path, os.environ)


def main(argv: Sequence[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    brand.activate(brand.JITERA)  # before any upstream module is imported
    load_env_file()
    prepare_environment(os.environ)

    reason = blocked_reason(args)
    if reason:
        sys.exit(f"{brand.current().command}: {reason}")

    from strix.jitera.commands import COMMANDS

    if args and args[0] in COMMANDS:
        sys.exit(COMMANDS[args[0]](args[1:]))

    install_user_agent()
    register_extensions()

    from strix.interface.main import main as strix_main

    strix_main()
