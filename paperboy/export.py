"""Export paper lists to BibTeX or CSV."""
from __future__ import annotations

import csv
import io
import re

from paperboy.models import Paper, SourceKind


def _bibtex_key(paper: Paper) -> str:
    slug = re.sub(r'[^a-zA-Z0-9_]', '_', paper.id)
    first_author = paper.authors[0].split()[-1].lower() if paper.authors else "unknown"
    year = paper.published.year
    first_word = re.sub(r'[^a-z]', '', paper.title.split()[0].lower()) if paper.title else "paper"
    return f"{first_author}{year}{first_word}"


def paper_to_bibtex(paper: Paper) -> str:
    """Format a single Paper as a BibTeX entry."""
    entry_types = {
        SourceKind.ARXIV: "misc",
        SourceKind.OPENREVIEW: "inproceedings",
        SourceKind.JOURNAL: "article",
    }
    entry_type = entry_types.get(paper.kind, "misc")
    key = _bibtex_key(paper)

    authors = " and ".join(paper.authors) if paper.authors else "Unknown"
    url = paper.pdf_url or paper.html_url or ""

    fields: list[tuple[str, str]] = [
        ("author", authors),
        ("title", "{" + paper.title + "}"),
        ("year", str(paper.published.year)),
        ("url", url),
        ("note", paper.source),
    ]
    if paper.venue:
        fields.append(("booktitle" if entry_type == "inproceedings" else "journal", "{" + paper.venue + "}"))
    if paper.abstract:
        abstract_oneline = paper.abstract.replace('\n', ' ').replace('{', '(').replace('}', ')')
        fields.append(("abstract", "{" + abstract_oneline[:400] + ("..." if len(paper.abstract) > 400 else "") + "}"))

    body = ",\n  ".join(f"{k} = {{{v}}}" if not v.startswith("{") else f"{k} = {v}" for k, v in fields)
    return f"@{entry_type}{{{key},\n  {body}\n}}"


def to_bibtex(papers: list[Paper]) -> str:
    """Format a list of papers as a BibTeX file."""
    return "\n\n".join(paper_to_bibtex(p) for p in papers)


def to_csv(papers: list[Paper]) -> str:
    """Format a list of papers as CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "title", "authors", "source", "published", "pdf_url", "citation_count"])
    for p in papers:
        writer.writerow([
            p.id,
            p.title,
            "; ".join(p.authors),
            p.source,
            p.published.strftime("%Y-%m-%d"),
            p.pdf_url or "",
            "" if p.citation_count is None else str(p.citation_count),
        ])
    return buf.getvalue()
