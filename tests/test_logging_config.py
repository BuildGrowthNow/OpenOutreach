import logging

from openoutreach.core.logging import configure_logging


def test_configure_logging_silences_noisy_third_party_loggers() -> None:
    root = logging.getLogger()
    pymongo_logger = logging.getLogger("pymongo")
    topology_logger = logging.getLogger("pymongo.topology")

    root.setLevel(logging.DEBUG)
    pymongo_logger.setLevel(logging.DEBUG)
    topology_logger.setLevel(logging.DEBUG)

    configure_logging(level=logging.INFO)

    assert root.level == logging.INFO
    assert pymongo_logger.getEffectiveLevel() == logging.WARNING
    assert topology_logger.getEffectiveLevel() == logging.WARNING
