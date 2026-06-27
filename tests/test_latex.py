"""Tests for LaTeX stripping."""
from paperboy.latex import strip_latex


def test_inline_math_stripped():
    assert strip_latex("We show $x^2 + y^2 = z^2$ holds.") == "We show x^2 + y^2 = z^2 holds."


def test_display_math_stripped():
    result = strip_latex("Equation: $$\\alpha + \\beta$$.")
    assert "alpha" in result or "+" in result
    assert "$$" not in result


def test_textbf_unwrapped():
    assert strip_latex("\\textbf{important}") == "important"


def test_emph_unwrapped():
    assert strip_latex("\\emph{emphasis}") == "emphasis"


def test_bare_command_removed():
    result = strip_latex("value \\infty end")
    assert "\\infty" not in result


def test_stray_braces_removed():
    assert "{" not in strip_latex("{hello}")
    assert "}" not in strip_latex("{hello}")


def test_plain_text_unchanged():
    text = "This is plain text with no LaTeX."
    assert strip_latex(text) == text
