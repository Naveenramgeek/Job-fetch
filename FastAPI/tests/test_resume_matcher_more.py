import app.services.resume_matcher as rm


def test_resume_to_full_text_and_fallback_json():
    text = rm._resume_to_full_text(
        {
            "experience": [{"title": "Eng", "company": "ACME", "start": "2020", "end": "2021", "bullets": ["Built APIs"]}],
            "projects": [{"name": "P", "bullets": ["Did X"]}],
        }
    )
    assert "Experience:" in text and "Projects:" in text
    text2 = rm._resume_to_full_text({})
    assert text2 == ""


def test_parse_date_token_and_gate_helpers():
    assert rm._parse_date_token_to_year_month("Jan 2020") == (2020, 1)
    assert rm._parse_date_token_to_year_month("2021") == (2021, 1)
    assert rm._parse_date_token_to_year_month("bad") is None
    assert rm._is_hard_gate_blocked(2.0, 5.0, 1.0) is True
    assert rm._is_hard_gate_blocked(None, 5.0, 1.0) is False


def test_fallback_keyword_score_handles_empty_and_overlap():
    assert rm._fallback_keyword_score("", "x") == 0.35
    s = rm._fallback_keyword_score("python fastapi postgres", "need python fastapi postgres")
    assert s > 0.35


def test_extract_required_years_range_pattern():
    jd = "Looking for 3-5 years of experience and minimum of 2 years in cloud."
    assert rm._extract_required_years_from_jd(jd) == 3.0 or rm._extract_required_years_from_jd(jd) == 5.0
