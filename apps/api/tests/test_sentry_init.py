from classroom_downloader.main import _scrub_sentry_event, app


def test_app_imports_without_sentry_dsn() -> None:
    assert app.title == "Educator Prime API"


def test_scrub_sentry_event_redacts_sensitive_shapes() -> None:
    event = {
        "extra": {"refresh_token": "secret", "nested": {"email": "ana@example.edu"}},
        "contexts": {"auth": {"access_token": "secret"}},
        "breadcrumbs": {
            "values": [
                {"data": {"client_secret": "secret", "safe": "kept"}},
                {"data": ["unexpected"]},
            ]
        },
    }

    scrubbed = _scrub_sentry_event(event, hint=object())

    assert scrubbed["extra"]["refresh_token"] == "<redacted>"
    assert scrubbed["extra"]["nested"]["email"] == "<redacted>"
    assert scrubbed["contexts"]["auth"]["access_token"] == "<redacted>"
    assert scrubbed["breadcrumbs"]["values"][0]["data"]["client_secret"] == "<redacted>"
    assert scrubbed["breadcrumbs"]["values"][0]["data"]["safe"] == "kept"


def test_scrub_sentry_event_never_raises_on_weird_shapes() -> None:
    event = {"extra": object(), "contexts": None, "breadcrumbs": {"values": [object()]}}

    assert _scrub_sentry_event(event, hint=None) is event
