from __future__ import annotations

from utils import normalize_doi, normalize_issn, safe_json_loads


def test_normalize_doi() -> None:
    assert normalize_doi("https://doi.org/10.1000/ABC") == "10.1000/abc"


def test_normalize_issn() -> None:
    assert normalize_issn("1234567X") == "1234-567X"


def test_safe_json_loads() -> None:
    assert safe_json_loads('{"a": 1}') == {"a": 1}
