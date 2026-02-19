import app.services.email_service as es


def test_send_email_returns_false_when_mailgun_not_configured(monkeypatch):
    monkeypatch.setattr(es.settings, "mailgun_api_key", None)
    monkeypatch.setattr(es.settings, "mailgun_domain", None)
    monkeypatch.setattr(es.settings, "mailgun_from_email", None)

    ok = es.send_email(to_email="user@example.com", subject="Hi", text="Body")
    assert ok is False


def test_send_email_success_when_configured(monkeypatch):
    monkeypatch.setattr(es.settings, "mailgun_api_key", "key")
    monkeypatch.setattr(es.settings, "mailgun_domain", "mg.example.com")
    monkeypatch.setattr(es.settings, "mailgun_from_email", "Alerts <alerts@example.com>")

    seen = {}

    class _Resp:
        def raise_for_status(self):
            return None

    def fake_post(url, auth, data, timeout):
        seen["url"] = url
        seen["auth"] = auth
        seen["data"] = data
        seen["timeout"] = timeout
        return _Resp()

    monkeypatch.setattr(es.httpx, "post", fake_post)
    ok = es.send_email(to_email="user@example.com", subject="Hi", text="Body")

    assert ok is True
    assert seen["url"] == "https://api.mailgun.net/v3/mg.example.com/messages"
    assert seen["auth"] == ("api", "key")
    assert seen["data"]["to"] == ["user@example.com"]
    assert seen["timeout"] == 15.0


def test_send_email_returns_false_when_provider_fails(monkeypatch):
    monkeypatch.setattr(es.settings, "mailgun_api_key", "key")
    monkeypatch.setattr(es.settings, "mailgun_domain", "mg.example.com")
    monkeypatch.setattr(es.settings, "mailgun_from_email", "Alerts <alerts@example.com>")

    def fake_post(url, auth, data, timeout):
        raise RuntimeError("network down")

    monkeypatch.setattr(es.httpx, "post", fake_post)
    ok = es.send_email(to_email="user@example.com", subject="Hi", text="Body")
    assert ok is False


def test_activation_and_reset_wrappers_build_expected_messages(monkeypatch):
    monkeypatch.setattr(es.settings, "activation_token_expire_minutes", 1440)
    monkeypatch.setattr(es.settings, "reset_password_token_expire_minutes", 30)
    captured = []

    def fake_send_email(*, to_email, subject, text):
        captured.append((to_email, subject, text))
        return True

    monkeypatch.setattr(es, "send_email", fake_send_email)

    assert es.send_activation_email(to_email="a@example.com", activation_link="https://app/activate?t=1") is True
    assert es.send_reset_password_email(to_email="a@example.com", reset_link="https://app/reset?t=1") is True

    assert "Activate your JobFetch account" in captured[0][1]
    assert "https://app/activate?t=1" in captured[0][2]
    assert "1440" in captured[0][2]

    assert "Reset your JobFetch password" in captured[1][1]
    assert "https://app/reset?t=1" in captured[1][2]
    assert "30" in captured[1][2]
