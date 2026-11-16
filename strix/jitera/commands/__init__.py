"""Subcommands of the ``jitera-pentest`` CLI that upstream Strix does not have.

Add a module with ``def run(argv: list[str]) -> int`` and register it in
``COMMANDS``. ``jitera-pentest <name> ...`` then runs it instead of the Strix CLI.
Upstream already uses: view, auth, completion(s), cloud.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from strix.jitera.commands import about


if TYPE_CHECKING:
    from collections.abc import Callable


COMMANDS: dict[str, Callable[[list[str]], int]] = {
    "about": about.run,
}
