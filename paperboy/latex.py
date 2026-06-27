"""Lightweight LaTeX → plain-text stripping for paper abstracts."""
from __future__ import annotations

import re

_PIPELINE: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'\$\$(.+?)\$\$', re.DOTALL), r'\1'),
    (re.compile(r'\$(.+?)\$', re.DOTALL), r'\1'),
    (re.compile(r'\\(?:textbf|textit|emph|text|mathrm|mathit|mathbf)\{(.+?)\}', re.DOTALL), r'\1'),
    (re.compile(r'\\[a-zA-Z]+\{(.+?)\}', re.DOTALL), r'\1'),
    (re.compile(r'\\[a-zA-Z]+'), ''),
    (re.compile(r'[{}]'), ''),
    (re.compile(r'\s{2,}'), ' '),
]


def strip_latex(text: str) -> str:
    """Return text with common LaTeX markup removed."""
    for pattern, repl in _PIPELINE:
        text = pattern.sub(repl, text)
    return text.strip()
