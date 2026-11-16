from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from strix.jitera import brand


if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _restore_brand() -> Iterator[None]:
    """Tests may activate JITERA; put UPSTREAM back so upstream tests are unaffected."""
    yield
    brand.activate(brand.UPSTREAM)
