"""``jitera about``: product name, version, and what it is built on."""

from __future__ import annotations

import sys

from strix.jitera import brand
from strix.jitera.bootstrap import package_version


def run(argv: list[str]) -> int:
    if argv:
        sys.stderr.write("usage: jitera about\n")
        return 2
    profile = brand.current()
    sys.stdout.write(
        f"{profile.name} {package_version()}\n"
        f"{profile.homepage}\n"
        f"Built on Strix (https://github.com/usestrix/strix), Apache-2.0.\n",
    )
    return 0
