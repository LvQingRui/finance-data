"""NL2SQL acceptance test cases."""

import pytest

from tests.nl2sql_queries import ACCEPTANCE_QUERIES


def test_acceptance_queries_defined():
    assert len(ACCEPTANCE_QUERIES) >= 12


@pytest.mark.parametrize("query", ACCEPTANCE_QUERIES)
def test_acceptance_query_format(query: str):
    assert query.strip()
    assert len(query) >= 4
