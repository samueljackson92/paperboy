"""Tests for BibTeX and CSV export."""
from datetime import datetime, timezone

from paperboy.export import paper_to_bibtex, to_bibtex, to_csv
from paperboy.models import Paper, SourceKind


def _paper(idx: int = 1, kind: SourceKind = SourceKind.ARXIV) -> Paper:
    return Paper(
        id=f"arxiv:2401.0000{idx}",
        title=f"Test Paper {idx}",
        authors=["Alice Smith", "Bob Jones"],
        abstract="An abstract.",
        source="arXiv",
        kind=kind,
        published=datetime(2024, 1, idx, tzinfo=timezone.utc),
        pdf_url=f"https://arxiv.org/pdf/2401.0000{idx}",
    )


def test_bibtex_entry_type_arxiv():
    bib = paper_to_bibtex(_paper(kind=SourceKind.ARXIV))
    assert bib.startswith("@misc{")


def test_bibtex_entry_type_openreview():
    p = _paper(kind=SourceKind.OPENREVIEW)
    bib = paper_to_bibtex(p)
    assert bib.startswith("@inproceedings{")


def test_bibtex_entry_type_journal():
    p = _paper(kind=SourceKind.JOURNAL)
    bib = paper_to_bibtex(p)
    assert bib.startswith("@article{")


def test_bibtex_contains_title():
    bib = paper_to_bibtex(_paper())
    assert "Test Paper" in bib


def test_bibtex_contains_authors():
    bib = paper_to_bibtex(_paper())
    assert "Alice Smith" in bib
    assert "Bob Jones" in bib


def test_bibtex_contains_year():
    bib = paper_to_bibtex(_paper())
    assert "2024" in bib


def test_to_bibtex_multiple():
    papers = [_paper(1), _paper(2)]
    bib = to_bibtex(papers)
    assert bib.count("@misc{") == 2


def test_csv_header():
    csv_str = to_csv([_paper()])
    first_line = csv_str.splitlines()[0]
    assert "title" in first_line
    assert "authors" in first_line


def test_csv_row_count():
    csv_str = to_csv([_paper(1), _paper(2)])
    lines = [l for l in csv_str.splitlines() if l]
    assert len(lines) == 3  # header + 2 rows


def test_csv_citation_count_empty_when_none():
    csv_str = to_csv([_paper()])
    data_line = csv_str.splitlines()[1]
    # citation_count field should be empty string
    assert data_line.endswith(",")
