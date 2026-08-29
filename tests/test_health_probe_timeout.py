from openoutreach.mongodb import connection


def test_mongodb_probe_forwards_optional_timeout(monkeypatch):
    calls = []

    monkeypatch.setattr(connection, "_is_mongodb_enabled", lambda: True)
    monkeypatch.setattr(connection, "_get_mongodb_uri", lambda: "mongodb://example")
    monkeypatch.setattr(connection.mongodb_connection, "_client", None)
    monkeypatch.setattr(connection.mongodb_connection, "_database", None)
    monkeypatch.setattr(
        connection.mongodb_connection,
        "connect",
        lambda **kwargs: calls.append(kwargs) or False,
    )

    assert connection.check_mongodb_connection(timeout_ms=5000) is False
    assert calls == [{"timeout_ms": 5000}]
