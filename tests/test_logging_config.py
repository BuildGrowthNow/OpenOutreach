import logging

from openoutreach.core.logging import configure_logging, redact_log_text


def test_configure_logging_silences_noisy_third_party_loggers() -> None:
    root = logging.getLogger()
    pymongo_logger = logging.getLogger("pymongo")
    topology_logger = logging.getLogger("pymongo.topology")

    root.setLevel(logging.DEBUG)
    pymongo_logger.setLevel(logging.DEBUG)
    topology_logger.setLevel(logging.DEBUG)

    configure_logging(level=logging.INFO)

    assert root.level == logging.INFO
    # MongoDB driver logs (heartbeats, topology, etc.) are set to CRITICAL
    # to suppress DEBUG messages like "Server heartbeat started"
    # Only ERROR and CRITICAL messages will be visible
    assert pymongo_logger.getEffectiveLevel() == logging.CRITICAL
    assert topology_logger.getEffectiveLevel() == logging.CRITICAL


def test_redact_log_text_removes_contact_credentials_and_url_queries() -> None:
    raw = "user=a.person@example.com phone=+1 (555) 123-4567 " \
        "Authorization: Bearer abc.def?x=y https://example.test/callback?code=secret"

    redacted = redact_log_text(raw)

    assert "a.person@example.com" not in redacted
    assert "555" not in redacted
    assert "Bearer abc.def" not in redacted
    assert "?code=secret" not in redacted
    assert "[REDACTED]" in redacted
