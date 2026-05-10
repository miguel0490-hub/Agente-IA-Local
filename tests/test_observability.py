from src.core import observability


def test_redact_text_masks_secrets():
    value = "api_key=abc token: xyz password = qwe"
    out = observability._redact_text(value)
    assert "[REDACTED]" in out
    assert "abc" not in out
    assert "xyz" not in out
    assert "qwe" not in out


def test_before_send_redacts_message_and_exception():
    event = {
        "message": "token=secret",
        "exception": {"values": [{"value": "password=secret2"}]},
    }
    out = observability._before_send(event, None)
    assert "secret" not in out["message"]
    assert "secret2" not in out["exception"]["values"][0]["value"]


def test_init_observability_returns_false_without_sdk(monkeypatch):
    monkeypatch.setattr(observability, "sentry_sdk", None)
    assert observability.init_observability() is False


def test_init_observability_returns_false_without_dsn(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "")
    monkeypatch.setattr(observability, "sentry_sdk", object())
    assert observability.init_observability() is False


def test_init_observability_initializes_sdk(monkeypatch):
    class DummySentry:
        def __init__(self):
            self.kwargs = None

        def init(self, **kwargs):
            self.kwargs = kwargs

    sdk = DummySentry()
    monkeypatch.setattr(observability, "sentry_sdk", sdk)
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.local/1")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.5")
    assert observability.init_observability() is True
    assert sdk.kwargs["environment"] == "test"
    assert sdk.kwargs["traces_sample_rate"] == 0.5
