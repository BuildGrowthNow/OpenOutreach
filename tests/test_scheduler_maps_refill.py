from unittest.mock import MagicMock


def _make_campaign(lead_source="google_maps", maps_query="plumbers NYC"):
    c = MagicMock()
    c.pk = "camp-001"
    c.lead_source = lead_source
    c.maps_query = maps_query
    c.maps_country_code = "US"
    c.maps_backends = None
    return c


def test_scrape_triggers_when_active_leads_below_threshold(monkeypatch):
    from openoutreach.core import scheduler
    from openoutreach.core.scheduler import MAPS_REFILL_THRESHOLD

    campaign = _make_campaign()
    mock_col = MagicMock()
    mock_col.count_documents.return_value = 5  # below threshold

    monkeypatch.setattr(
        "openoutreach.mongodb.connection.get_mongodb_collection",
        lambda name: mock_col if name == "deals" else None,
    )

    started = []

    def fake_thread_init(self, target=None, daemon=None, name=None):
        self._target = target

    def fake_thread_start(self):
        started.append(True)

    monkeypatch.setattr("threading.Thread.__init__", fake_thread_init)
    monkeypatch.setattr("threading.Thread.start", fake_thread_start)

    scheduler._maybe_trigger_maps_scrape(campaign, "user-001")
    assert len(started) == 1


def test_scrape_suppressed_when_active_leads_above_threshold(monkeypatch):
    from openoutreach.core import scheduler
    from openoutreach.core.scheduler import MAPS_REFILL_THRESHOLD

    campaign = _make_campaign()
    mock_col = MagicMock()
    mock_col.count_documents.return_value = MAPS_REFILL_THRESHOLD + 5

    monkeypatch.setattr(
        "openoutreach.mongodb.connection.get_mongodb_collection",
        lambda name: mock_col if name == "deals" else None,
    )

    started = []

    def fake_thread_init(self, target=None, daemon=None, name=None):
        self._target = target

    def fake_thread_start(self):
        started.append(True)

    monkeypatch.setattr("threading.Thread.__init__", fake_thread_init)
    monkeypatch.setattr("threading.Thread.start", fake_thread_start)

    scheduler._maybe_trigger_maps_scrape(campaign, "user-001")
    assert len(started) == 0


def test_scrape_suppressed_when_already_running(monkeypatch):
    from openoutreach.core import scheduler

    campaign = _make_campaign()
    scheduler._maps_scraping.add(campaign.pk)

    mock_col = MagicMock()
    mock_col.count_documents.return_value = 0

    monkeypatch.setattr(
        "openoutreach.mongodb.connection.get_mongodb_collection",
        lambda name: mock_col,
    )

    started = []

    def fake_thread_init(self, target=None, daemon=None, name=None):
        self._target = target

    def fake_thread_start(self):
        started.append(True)

    monkeypatch.setattr("threading.Thread.__init__", fake_thread_init)
    monkeypatch.setattr("threading.Thread.start", fake_thread_start)

    scheduler._maybe_trigger_maps_scrape(campaign, "user-001")
    assert len(started) == 0
    scheduler._maps_scraping.discard(campaign.pk)
