from __future__ import annotations

from filter import SsciWhitelist, _extract_whitelist_values
from utils import Paper


def test_whitelist_extracts_metadata_from_common_headers() -> None:
    rows = [
        [
            "journal_name",
            "ISSN",
            "eISSN",
            "JIF",
            "JCR quartile",
            "CiteScore",
            "Publisher",
            "Category",
        ],
        [
            "Learning and Instruction",
            "0959-4752",
            "1873-3263",
            "6.2",
            "Q1",
            "9.1",
            "Elsevier",
            "Education & Educational Research; Psychology",
        ],
    ]

    names, issns, journal_categories, issn_categories, journal_metadata, issn_metadata = _extract_whitelist_values(rows)

    assert "learning instruction" in names
    assert {"0959-4752", "1873-3263"} <= issns
    assert journal_categories["learning instruction"] == ["Education & Educational Research", "Psychology"]
    assert issn_categories["0959-4752"] == ["Education & Educational Research", "Psychology"]
    assert journal_metadata["learning instruction"]["impact_factor"] == "6.2"
    assert journal_metadata["learning instruction"]["quartile"] == "Q1"
    assert journal_metadata["learning instruction"]["citescore"] == "9.1"
    assert journal_metadata["learning instruction"]["publisher"] == "Elsevier"


def test_whitelist_apply_metadata_to_matching_paper() -> None:
    whitelist = SsciWhitelist(
        journal_names={"learning instruction"},
        issns={"0959-4752"},
        journal_metadata={
            "learning instruction": {
                "impact_factor": "6.2",
                "quartile": "Q1",
                "citescore": "9.1",
                "publisher": "Elsevier",
                "categories": ["Education & Educational Research"],
            }
        },
    )
    paper = Paper(title="AI in primary mathematics", journal="Learning and Instruction", issns=["09594752"])

    assert whitelist.is_match(paper)

    whitelist.apply_metadata(paper)

    assert paper.impact_factor == "6.2"
    assert paper.quartile == "Q1"
    assert paper.citescore == "9.1"
    assert paper.publisher == "Elsevier"
    assert paper.ssci_categories == ["Education & Educational Research"]

