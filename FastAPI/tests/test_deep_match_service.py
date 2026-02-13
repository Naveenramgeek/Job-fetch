import app.services.deep_match_service as dm


class _User:
    def __init__(self, user_id, is_active=True, search_category_id="c1"):
        self.id = user_id
        self.is_active = is_active
        self.search_category_id = search_category_id


class _Resume:
    def __init__(self, parsed):
        self.parsed_data = parsed


class _Job:
    def __init__(self, job_id, title="Backend Engineer", description="desc"):
        self.id = job_id
        self.title = title
        self.description = description


def test_run_deep_match_for_category_no_users_or_jobs(monkeypatch):
    monkeypatch.setattr(dm, "get_users_by_category", lambda db, cid: [])
    monkeypatch.setattr(dm, "get_jobs_by_category_since", lambda db, cid, since_hours: [])
    out = dm.run_deep_match_for_category(db=object(), search_category_id="c1")
    assert out == {"users": 0, "jobs": 0, "scored": 0}


def test_run_deep_match_for_category_skips_existing_and_low_scores(monkeypatch):
    monkeypatch.setattr(dm, "get_users_by_category", lambda db, cid: [_User("u1")])
    monkeypatch.setattr(dm, "get_jobs_by_category_since", lambda db, cid, since_hours: [_Job("j1"), _Job("j2"), _Job("j3")])
    monkeypatch.setattr(dm, "get_latest_by_user", lambda db, uid: _Resume({"experience": []}))
    monkeypatch.setattr(dm, "get_existing_match", lambda db, uid, jid: jid == "j1")

    def fake_score(resume_data, title, description):
        if "j2" in description:
            return {"match_score": 70.0, "match_reason": "low", "hard_gate_blocked": False}
        return {"match_score": 95.0, "match_reason": "great", "hard_gate_blocked": False, "resume_years_experience": 5.0}

    monkeypatch.setattr(dm, "_score_pair", lambda resume_data, title, description: fake_score(resume_data, title, description))
    created = []
    monkeypatch.setattr(dm, "create_match", lambda db, **kwargs: created.append(kwargs))

    # Mark descriptions so fake_score can branch.
    monkeypatch.setattr(dm, "get_jobs_by_category_since", lambda db, cid, since_hours: [_Job("j1", description="j1"), _Job("j2", description="j2"), _Job("j3", description="j3")])
    out = dm.run_deep_match_for_category(db=object(), search_category_id="c1")
    assert out["scored"] == 1
    assert len(created) == 1
    assert created[0]["job_listing_id"] == "j3"


def test_run_deep_match_all_aggregates(monkeypatch):
    class _Cat:
        def __init__(self, cat_id):
            self.id = cat_id

    monkeypatch.setattr("app.repos.search_category_repo.get_all", lambda db: [_Cat("c1"), _Cat("c2")])
    monkeypatch.setattr(dm, "run_deep_match_for_category", lambda db, cat_id: {"users": 1, "jobs": 2, "scored": 3})
    out = dm.run_deep_match_all(db=object())
    assert out == {"users": 2, "jobs": 4, "scored": 6}


def test_run_deep_match_for_user_guard_rails(monkeypatch):
    db = object()
    monkeypatch.setattr(dm, "get_by_id", lambda _db, _uid: None)
    assert dm.run_deep_match_for_user(db, "u-missing")["reason"] == "user_not_found"

    monkeypatch.setattr(dm, "get_by_id", lambda _db, _uid: _User("u-inactive", is_active=False))
    assert dm.run_deep_match_for_user(db, "u-inactive")["reason"] == "user_inactive"

    monkeypatch.setattr(dm, "get_by_id", lambda _db, _uid: _User("u-no-cat", search_category_id=None))
    assert dm.run_deep_match_for_user(db, "u-no-cat")["reason"] == "missing_search_category"


def test_run_deep_match_for_user_no_recent_jobs(monkeypatch):
    user = _User("u1", is_active=True, search_category_id="cat-1")
    monkeypatch.setattr(dm, "get_by_id", lambda db, uid: user)
    monkeypatch.setattr(dm, "get_jobs_by_category_since", lambda db, cid, since_hours: [])
    out = dm.run_deep_match_for_user(db=object(), user_id="u1", since_hours=15)
    assert out == {
        "user_id": "u1",
        "category_id": "cat-1",
        "jobs": 0,
        "scored": 0,
        "skipped_existing": 0,
        "skipped_low": 0,
    }


def test_run_deep_match_for_user_scores_and_returns_counts(monkeypatch):
    user = _User("u1", is_active=True, search_category_id="cat-1")
    jobs = [_Job("j1"), _Job("j2")]
    monkeypatch.setattr(dm, "get_by_id", lambda db, uid: user)
    monkeypatch.setattr(dm, "get_jobs_by_category_since", lambda db, cid, since_hours: jobs)

    calls = {"score_dist": None}

    def fake_score_user(db, user_obj, jobs_list):
        assert user_obj is user
        assert jobs_list == jobs
        return {
            "scored": 1,
            "skipped_existing": 1,
            "skipped_low": 0,
            "scores": [92.5],
            "low_score_samples": [],
        }

    monkeypatch.setattr(dm, "_score_user_against_jobs", fake_score_user)
    monkeypatch.setattr(dm, "_log_score_distribution", lambda scores, cid: calls.update(score_dist=(scores, cid)))

    out = dm.run_deep_match_for_user(db=object(), user_id="u1", since_hours=6)
    assert out == {
        "user_id": "u1",
        "category_id": "cat-1",
        "jobs": 2,
        "scored": 1,
        "skipped_existing": 1,
        "skipped_low": 0,
    }
    assert calls["score_dist"] == ([92.5], "cat-1")
