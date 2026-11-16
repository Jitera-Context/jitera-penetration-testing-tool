"""The patched upstream code reads the active brand profile.

Each check runs in a fresh interpreter so module-level constants are evaluated
under the profile we choose, without touching this test process.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from strix.jitera import brand


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


@pytest.mark.parametrize("profile", ["UPSTREAM", "JITERA"])
def test_sarif_tool_identity_follows_brand(profile: str) -> None:
    expected = getattr(brand, profile)
    got = _evaluate(
        profile,
        "__import__('strix.report.sarif', fromlist=['x']).TOOL_NAME",
    )
    assert got == expected.name


@pytest.mark.parametrize("profile", ["UPSTREAM", "JITERA"])
def test_llm_attribution_follows_brand(profile: str) -> None:
    expected = getattr(brand, profile)
    got = _evaluate(
        profile,
        "__import__('strix.config.models', fromlist=['x']).APP_ATTRIBUTION_HEADERS",
    )
    assert got == {"HTTP-Referer": expected.homepage, "X-Title": expected.name}
