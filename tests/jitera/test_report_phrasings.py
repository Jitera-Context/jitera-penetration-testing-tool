"""The scan report recognises how agents write up query-language injection.

Upstream added the query_language_injection skill without its phrasings, so a
report could claim the class was never tested when the agent had recorded it.
"""

from __future__ import annotations

import pytest

from tests.test_report_coverage import _document, _entry, _graph


def _gaps(risk_area: str) -> list[dict[str, object]]:
    doc = _document(
        entries=[_entry(risk_area=risk_area, surface="GET /api/search?filter=")],
        agent_graph=_graph(metadata={"agent-1": {"skills": ["query_language_injection"]}}),
    )
    return [gap for gap in doc["gaps"] if gap["kind"] == "unrecorded_risk_class"]


@pytest.mark.parametrize(
    "risk_area",
    [
        "Query-Language Injection",
        "JSONPath filter injection",
        "OData $filter injection",
        "LDAP injection",
        "XPath injection",
    ],
)
def test_a_recorded_query_language_test_is_not_reported_as_a_gap(risk_area: str) -> None:
    assert _gaps(risk_area) == []


def test_an_unrelated_row_still_leaves_the_gap() -> None:
    assert len(_gaps("Stored XSS")) == 1
