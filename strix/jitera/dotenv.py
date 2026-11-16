"""Load the tool's own ``.env`` file into the environment.

Only this tool's file is read: ``JITERA_PENTEST_ENV_FILE`` if set, otherwise
the ``.env`` next to the source checkout. Never the current directory's
``.env``, which during a scan is usually the scanned project's and may hold
unrelated keys such as ``OPENAI_API_KEY``.

Values never override the real environment, and empty values are skipped, so
an unfilled template line can't clear a setting saved in ~/.strix.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import MutableMapping


ENV_FILE_VAR = "JITERA_PENTEST_ENV_FILE"
_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def default_env_file() -> Path:
    explicit = os.environ.get(ENV_FILE_VAR, "").strip()
    if explicit:
        return Path(explicit).expanduser()
    # strix/jitera/dotenv.py -> the checkout root
    return Path(__file__).resolve().parents[2] / ".env"


def _value(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        return raw[1:-1]
    # An unquoted value ends at a " #" comment.
    comment = re.search(r"\s#", raw)
    return raw[: comment.start()].rstrip() if comment else raw


def parse(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines. Skips comments, blank lines, bad keys and empty values."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        stripped = stripped.removeprefix("export ").lstrip()
        key, _, raw = stripped.partition("=")
        key = key.strip()
        value = _value(raw)
        if _KEY.match(key) and value:
            values[key] = value
    return values


def load(path: Path, env: MutableMapping[str, str]) -> list[str]:
    """Apply ``path`` to ``env`` without overriding what's set. Returns the keys set."""
    if not path.is_file():
        return []
    applied = []
    for key, value in parse(path.read_text(encoding="utf-8")).items():
        if key not in env:
            env[key] = value
            applied.append(key)
    return applied
