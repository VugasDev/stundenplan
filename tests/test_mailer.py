from app import mailer


def test_token_roundtrip(app):
    with app.app_context():
        token = mailer.generate_confirm_token("a@b.de")
        assert mailer.confirm_token(token) == "a@b.de"


def test_token_rejects_tampering(app):
    with app.app_context():
        assert mailer.confirm_token("kaputt.kaputt.kaputt") is None


def test_token_expires(app):
    with app.app_context():
        token = mailer.generate_confirm_token("a@b.de")
        assert mailer.confirm_token(token, max_age_seconds=-1) is None


def test_send_confirmation_records_message(app):
    from app.extensions import mail
    with app.app_context():
        with mail.record_messages() as outbox:
            mailer.send_confirmation("a@b.de", "https://x/confirm/abc")
        assert len(outbox) == 1
        assert "https://x/confirm/abc" in outbox[0].body
        assert outbox[0].recipients == ["a@b.de"]
