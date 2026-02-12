from pathlib import Path

import pytest

import app.services.latex_render_service as lrs


def test_resolve_pdflatex_binary_fallback(monkeypatch):
    monkeypatch.setattr(lrs.shutil, "which", lambda name: None)
    monkeypatch.setattr(Path, "exists", lambda self: str(self) == "/Library/TeX/texbin/pdflatex")
    assert lrs._resolve_pdflatex_binary() == "/Library/TeX/texbin/pdflatex"


def test_render_latex_to_pdf_bytes_raises_when_missing_binary(monkeypatch):
    monkeypatch.setattr(lrs, "_resolve_pdflatex_binary", lambda: None)
    with pytest.raises(RuntimeError):
        lrs.render_latex_to_pdf_bytes("\\documentclass{article}")


def test_render_latex_to_pdf_bytes_compile_failure(monkeypatch):
    monkeypatch.setattr(lrs, "_resolve_pdflatex_binary", lambda: "/usr/bin/pdflatex")

    class _Proc:
        returncode = 1
        stderr = "latex error"
        stdout = ""

    monkeypatch.setattr(lrs.subprocess, "run", lambda *args, **kwargs: _Proc())
    with pytest.raises(RuntimeError):
        lrs.render_latex_to_pdf_bytes("\\documentclass{article}")
