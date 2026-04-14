import pytest

from glean.triggers.pre_signup import handler


def _make_event(email: str) -> dict:
    return {
        "request": {"userAttributes": {"email": email}},
        "response": {},
    }


class TestPreSignupHandler:
    def test_allows_any_email_when_allowlist_empty(self, monkeypatch):
        monkeypatch.delenv("ALLOWED_EMAILS", raising=False)
        event = _make_event("anyone@example.com")
        result = handler(event, None)
        assert result["response"]["autoConfirmUser"] is True
        assert result["response"]["autoVerifyEmail"] is True

    def test_allows_email_on_allowlist(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_EMAILS", "alice@gmail.com,bob@gmail.com")
        event = _make_event("alice@gmail.com")
        result = handler(event, None)
        assert result["response"]["autoConfirmUser"] is True
        assert result["response"]["autoVerifyEmail"] is True

    def test_rejects_email_not_on_allowlist(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_EMAILS", "alice@gmail.com")
        event = _make_event("mallory@evil.com")
        with pytest.raises(Exception, match="not in the allowlist"):
            handler(event, None)

    def test_allowlist_is_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_EMAILS", "Alice@Gmail.com")
        event = _make_event("alice@gmail.com")
        result = handler(event, None)
        assert result["response"]["autoConfirmUser"] is True

    def test_handles_whitespace_in_allowlist(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_EMAILS", " alice@gmail.com , bob@gmail.com ")
        event = _make_event("bob@gmail.com")
        result = handler(event, None)
        assert result["response"]["autoConfirmUser"] is True

    def test_allows_all_when_allowlist_is_empty_string(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_EMAILS", "")
        event = _make_event("anyone@example.com")
        result = handler(event, None)
        assert result["response"]["autoConfirmUser"] is True
