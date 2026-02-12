import shutil
import subprocess
import tempfile
import os
from pathlib import Path


def _resolve_pdflatex_binary() -> str | None:
    binary = shutil.which("pdflatex")
    if binary:
        return binary
    # Fallbacks for macOS installations where FastAPI process PATH is stale.
    candidates = [
        "/Library/TeX/texbin/pdflatex",
        "/usr/texbin/pdflatex",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def render_latex_to_pdf_bytes(latex: str) -> bytes:
    """
    Compile LaTeX into PDF bytes using local pdflatex.
    Raises RuntimeError if pdflatex is unavailable or compilation fails.
    """
    pdflatex_bin = _resolve_pdflatex_binary()
    if not pdflatex_bin:
        raise RuntimeError("pdflatex is not installed on the server")

    with tempfile.TemporaryDirectory(prefix="latex_render_") as tmpdir:
        tmp = Path(tmpdir)
        tex_path = tmp / "resume.tex"
        pdf_path = tmp / "resume.pdf"
        log_path = tmp / "resume.log"
        # Some resume templates include \input{glyphtounicode}; provide a local fallback.
        # This prevents hard failures when the TeX distribution does not ship this file.
        (tmp / "glyphtounicode.tex").write_text("\\pdfgentounicode=1\n", encoding="utf-8")
        tex_path.write_text(latex or "", encoding="utf-8")

        cmd = [
            pdflatex_bin,
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-output-directory",
            str(tmp),
            str(tex_path),
        ]
        env = os.environ.copy()
        tex_bin_dir = str(Path(pdflatex_bin).parent)
        env["PATH"] = f"{tex_bin_dir}:{env.get('PATH', '')}"
        proc = subprocess.run(
            cmd,
            cwd=str(tmp),
            capture_output=True,
            text=True,
            timeout=45,
            env=env,
        )

        if proc.returncode != 0 or not pdf_path.exists():
            detail = ""
            if log_path.exists():
                detail = log_path.read_text(encoding="utf-8", errors="ignore")[-2000:]
            elif proc.stderr:
                detail = proc.stderr[-2000:]
            elif proc.stdout:
                detail = proc.stdout[-2000:]
            raise RuntimeError(f"LaTeX compile failed. {detail}".strip())

        return pdf_path.read_bytes()
