from openoutreach.api_v2.routers.analytics import CampaignStats, OverviewStats


def test_campaign_stats_has_wa_fields():
    stats = CampaignStats(wa_messages_sent=5, wa_connections_sent=3)
    assert stats.wa_messages_sent == 5
    assert stats.wa_connections_sent == 3


def test_overview_stats_has_wa_fields():
    stats = OverviewStats(wa_messages_sent=10, wa_connections_sent=7)
    assert stats.wa_messages_sent == 10
    assert stats.wa_connections_sent == 7


def test_campaign_stats_wa_defaults_zero():
    stats = CampaignStats()
    assert stats.wa_messages_sent == 0
    assert stats.wa_connections_sent == 0


def test_campaign_stats_serialises_wa_aliases():
    stats = CampaignStats(wa_messages_sent=2, wa_connections_sent=1)
    d = stats.model_dump(by_alias=True)
    assert d["waMessagesSent"] == 2
    assert d["waConnectionsSent"] == 1
