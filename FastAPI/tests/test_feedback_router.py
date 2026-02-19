from datetime import datetime, timezone

import app.routers.feedback as feedback_mod


class _Feedback:
    def __init__(self):
        self.id = "f1"
        self.category = "General"
        self.message = "Great app, but improve search relevance."
        self.rating = 4
        self.page = "/dashboard"
        self.created_at = datetime.now(timezone.utc)


def test_submit_feedback_success(monkeypatch, client):
    monkeypatch.setattr(feedback_mod, "create_feedback", lambda db, **kwargs: _Feedback())
    resp = client.post(
        "/feedback",
        json={
            "category": "General",
            "message": "This is useful feedback for usability.",
            "rating": 5,
            "page": "/feedback",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "f1"
    assert body["rating"] == 4


def test_submit_feedback_failure_returns_500(monkeypatch, client):
    monkeypatch.setattr(feedback_mod, "create_feedback", lambda db, **kwargs: (_ for _ in ()).throw(RuntimeError("db error")))
    resp = client.post(
        "/feedback",
        json={"category": "Bug report", "message": "Valid message with enough length", "rating": 3},
    )
    assert resp.status_code == 500
    assert "Failed to submit feedback" in resp.json()["detail"]
