from pathlib import Path

import app.logging_config as lc
import app.services.latex_render_service as lrs


def test_setup_logging_string_level():
    lc.setup_logging("debug")
    import logging

    assert logging.getLogger().level <= logging.DEBUG


def test_setup_logging_with_none_level():
    lc.setup_logging(None)
    import logging

    assert isinstance(logging.getLogger().level, int)


def test_setup_logging_import_failure_falls_back(monkeypatch):
    import builtins

    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "app.config":
            raise RuntimeError("boom")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    lc.setup_logging(None)


def test_render_latex_to_pdf_bytes_success(monkeypatch):
    monkeypatch.setattr(lrs, "_resolve_pdflatex_binary", lambda: "/usr/bin/pdflatex")

    class _Proc:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(cmd, cwd, capture_output, text, timeout, env):
        Path(cwd, "resume.pdf").write_bytes(b"%PDF-1.4")
        return _Proc()

    monkeypatch.setattr(lrs.subprocess, "run", fake_run)
    out = lrs.render_latex_to_pdf_bytes("\\documentclass{article}")
    assert out.startswith(b"%PDF")


def test_render_latex_to_pdf_bytes_compile_failure_stdout_path(monkeypatch):
    monkeypatch.setattr(lrs, "_resolve_pdflatex_binary", lambda: "/usr/bin/pdflatex")

    class _Proc:
        returncode = 1
        stderr = ""
        stdout = "compile failed from stdout"

    monkeypatch.setattr(lrs.subprocess, "run", lambda *args, **kwargs: _Proc())
    try:
        lrs.render_latex_to_pdf_bytes("\\documentclass{article}")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
