import app.services.user_category_service as ucs


class _Cat:
    def __init__(self, cat_id, slug):
        self.id = cat_id
        self.slug = slug


class _Resume:
    def __init__(self, parsed_data):
        self.parsed_data = parsed_data


def test_extract_title_from_resume():
    t1, raw1 = ucs._extract_title_from_resume({"contact": {"title": "Backend Engineer"}})
    assert t1 == "backend engineer"
    assert raw1 == "Backend Engineer"
    t2, raw2 = ucs._extract_title_from_resume({"experience": [{"title": "Data Scientist"}]})
    assert t2 == "data scientist"
    assert raw2 == "Data Scientist"


def test_keyword_assign_category():
    slug = ucs._keyword_assign_category({"contact": {"title": "Senior Software Engineer"}}, ["software_engineer"])
    assert slug == "software_engineer"
    assert ucs._keyword_assign_category({"contact": {"title": "Unknown"}}, ["data_scientist"]) is None


def test_suggest_generic_slug_fallback():
    slug, name = ucs._suggest_generic_slug_from_title("UI/UX Lead Engineer")
    assert slug.startswith("ui_ux")
    assert "Ui/Ux" in name


def test_assign_user_category_keyword_match(monkeypatch):
    cats = [_Cat("c1", "software_engineer")]
    monkeypatch.setattr(ucs, "get_all", lambda db: cats)
    monkeypatch.setattr(ucs, "get_by_slug", lambda db, slug: cats[0])
    updated = {}
    monkeypatch.setattr(ucs, "update", lambda db, user_id, **kwargs: updated.update(kwargs))
    out = ucs.assign_user_category(
        db=object(),
        user_id="u1",
        resume_data={"contact": {"title": "Software Engineer"}},
    )
    assert out == "software_engineer"
    assert updated["search_category_id"] == "c1"


def test_assign_user_category_llm_map_existing(monkeypatch):
    cats = [_Cat("c1", "software_engineer"), _Cat("c2", "data_scientist")]
    monkeypatch.setattr(ucs, "get_all", lambda db: cats)
    monkeypatch.setattr(ucs, "is_llm_enabled", lambda: True)
    monkeypatch.setattr(ucs, "llm_assign_category_call", lambda title, slugs: "data_scientist")
    monkeypatch.setattr(ucs, "get_by_slug", lambda db, slug: next(c for c in cats if c.slug == slug))
    monkeypatch.setattr(ucs, "update", lambda db, user_id, **kwargs: None)
    out = ucs.assign_user_category(db=object(), user_id="u1", resume_data={"contact": {"title": "AI Research Lead"}})
    assert out == "data_scientist"


def test_assign_user_category_creates_new_when_missing(monkeypatch):
    cats = [_Cat("c1", "software_engineer")]
    monkeypatch.setattr(ucs, "get_all", lambda db: cats)
    monkeypatch.setattr(ucs, "is_llm_enabled", lambda: False)
    monkeypatch.setattr(ucs, "get_by_slug", lambda db, slug: None)
    monkeypatch.setattr(ucs, "create_category", lambda db, slug, display_name: _Cat("c9", slug))
    called = {}
    monkeypatch.setattr(ucs, "update", lambda db, user_id, **kwargs: called.update(kwargs))
    out = ucs.assign_user_category(
        db=object(),
        user_id="u1",
        resume_data={"contact": {"title": "Platform Reliability Specialist"}},
    )
    assert out == "platform_reliability_specialist"
    assert called["search_category_id"] == "c9"


def test_assign_user_category_uses_latest_resume_when_none(monkeypatch):
    cats = [_Cat("c1", "software_engineer")]
    monkeypatch.setattr(ucs, "get_all", lambda db: cats)
    monkeypatch.setattr(ucs, "get_latest_by_user", lambda db, uid: _Resume({"contact": {"title": "Software Engineer"}}))
    monkeypatch.setattr(ucs, "get_by_slug", lambda db, slug: cats[0])
    monkeypatch.setattr(ucs, "update", lambda db, user_id, **kwargs: None)
    out = ucs.assign_user_category(db=object(), user_id="u1", resume_data=None)
    assert out == "software_engineer"


def test_assign_user_category_unknown_title_returns_none(monkeypatch):
    cats = [_Cat("c1", "software_engineer"), _Cat("c2", "data_scientist")]
    monkeypatch.setattr(ucs, "get_all", lambda db: cats)
    monkeypatch.setattr(ucs, "is_llm_enabled", lambda: True)
    monkeypatch.setattr(ucs, "update", lambda db, user_id, **kwargs: (_ for _ in ()).throw(RuntimeError("must not update")))
    out = ucs.assign_user_category(db=object(), user_id="u1", resume_data={"contact": {"title": "Unknown Role"}})
    assert out is None


def test_assign_user_category_returns_none_when_no_category_created(monkeypatch):
    monkeypatch.setattr(ucs, "get_all", lambda db: [])
    monkeypatch.setattr(ucs, "is_llm_enabled", lambda: False)
    monkeypatch.setattr(ucs, "get_by_slug", lambda db, slug: None)
    monkeypatch.setattr(ucs, "create_category", lambda db, slug, display_name: None)
    out = ucs.assign_user_category(db=object(), user_id="u1", resume_data={"contact": {"title": "Any"}})
    assert out is None


def test_assign_user_category_llm_suggest_exception_uses_fallback(monkeypatch):
    cats = [_Cat("c1", "software_engineer")]
    monkeypatch.setattr(ucs, "get_all", lambda db: cats)
    monkeypatch.setattr(ucs, "is_llm_enabled", lambda: True)
    monkeypatch.setattr(ucs, "llm_assign_category_call", lambda title, slugs: None)
    monkeypatch.setattr(ucs, "llm_suggest_slug_call", lambda title: (_ for _ in ()).throw(RuntimeError("llm fail")))
    monkeypatch.setattr(ucs, "get_by_slug", lambda db, slug: None)
    monkeypatch.setattr(ucs, "create_category", lambda db, slug, display_name: _Cat("c9", slug))
    monkeypatch.setattr(ucs, "update", lambda db, user_id, **kwargs: None)
    out = ucs.assign_user_category(db=object(), user_id="u1", resume_data={"contact": {"title": "Growth Analyst"}})
    assert out == "growth_analyst"
