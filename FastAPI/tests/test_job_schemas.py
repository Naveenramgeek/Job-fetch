import pytest
from pydantic import ValidationError

from app.schemas.job import LatexRenderRequest, TailorResumeFromJdRequest


def test_tailor_resume_from_jd_request_validates_lengths():
    with pytest.raises(ValidationError):
        TailorResumeFromJdRequest(job_description="too short")

    req = TailorResumeFromJdRequest(job_description="A" * 100, job_title="Backend Engineer")
    assert req.job_title == "Backend Engineer"


def test_latex_render_request_requires_content():
    with pytest.raises(ValidationError):
        LatexRenderRequest(latex="")

    req = LatexRenderRequest(latex="\\documentclass{article}")
    assert req.latex.startswith("\\documentclass")
