from pathlib import Path

import pytest

import app.services.latex_render_service as lrs


def test_resolve_pdflatex_binary_fallback(monkeypatch):
    monkeypatch.setattr(lrs.shutil, "which", lambda name: None)
    monkeypatch.setattr(Path, "exists", lambda self: str(self) == "/Library/TeX/texbin/pdflatex")
    assert lrs._resolve_pdflatex_binary() == "/Library/TeX/texbin/pdflatex"


def test_resolve_pdflatex_binary_prefers_path_lookup(monkeypatch):
    monkeypatch.setattr(lrs.shutil, "which", lambda name: "/usr/local/bin/pdflatex")
    assert lrs._resolve_pdflatex_binary() == "/usr/local/bin/pdflatex"


def test_resolve_pdflatex_binary_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(lrs.shutil, "which", lambda name: None)
    monkeypatch.setattr(Path, "exists", lambda self: False)
    assert lrs._resolve_pdflatex_binary() is None


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


def test_validate_latex_security_allows_known_safe_input():
    safe = r"\documentclass{article}\input{glyphtounicode}\begin{document}ok\end{document}"
    out = lrs._validate_latex_security(safe)  # noqa: SLF001
    assert out == safe


def test_validate_latex_security_rejects_empty_and_too_large():
    with pytest.raises(RuntimeError):
        lrs._validate_latex_security("  ")  # noqa: SLF001
    with pytest.raises(RuntimeError):
        lrs._validate_latex_security("A" * (lrs.MAX_LATEX_CHARS + 1))  # noqa: SLF001


@pytest.mark.parametrize(
    "latex",
    [
        r"\documentclass{article}\include{secret}",
        r"\documentclass{article}\input{../../etc/passwd}",
        r"\documentclass{article}\input{secrets.tex}",
        r"\documentclass{article}\write18{ls}",
        r"\documentclass{article}\openin\in=foo",
    ],
)
def test_validate_latex_security_rejects_dangerous_patterns(latex):
    with pytest.raises(RuntimeError):
        lrs._validate_latex_security(latex)  # noqa: SLF001


def test_render_latex_to_pdf_bytes_rejects_unsafe_before_subprocess(monkeypatch):
    monkeypatch.setattr(lrs, "_resolve_pdflatex_binary", lambda: "/usr/bin/pdflatex")
    called = {"run": False}

    def _should_not_run(*args, **kwargs):
        called["run"] = True
        raise AssertionError("subprocess.run should not be called for unsafe latex")

    monkeypatch.setattr(lrs.subprocess, "run", _should_not_run)
    with pytest.raises(RuntimeError):
        lrs.render_latex_to_pdf_bytes(r"\documentclass{article}\write18{whoami}")
    assert called["run"] is False


def test_render_latex_to_pdf_bytes_compile_failure_uses_log_file(monkeypatch):
    monkeypatch.setattr(lrs, "_resolve_pdflatex_binary", lambda: "/usr/bin/pdflatex")

    class _Proc:
        returncode = 1
        stderr = ""
        stdout = ""

    def fake_run(cmd, cwd, capture_output, text, timeout, env):
        Path(cwd, "resume.log").write_text("failure from log", encoding="utf-8")
        return _Proc()

    monkeypatch.setattr(lrs.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError) as exc:
        lrs.render_latex_to_pdf_bytes("\\documentclass{article}")
    assert "failure from log" in str(exc.value)


def test_render_latex_to_pdf_bytes_compile_failure_without_output_detail(monkeypatch):
    monkeypatch.setattr(lrs, "_resolve_pdflatex_binary", lambda: "/usr/bin/pdflatex")

    class _Proc:
        returncode = 1
        stderr = ""
        stdout = ""

    monkeypatch.setattr(lrs.subprocess, "run", lambda *args, **kwargs: _Proc())
    with pytest.raises(RuntimeError) as exc:
        lrs.render_latex_to_pdf_bytes("\\documentclass{article}")
    assert "LaTeX compile failed." in str(exc.value)
