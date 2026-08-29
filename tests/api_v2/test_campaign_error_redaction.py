from pathlib import Path


def test_campaign_routes_do_not_return_raw_exceptions():
    source = (
        Path(__file__).parents[2]
        / "openoutreach"
        / "api_v2"
        / "routers"
        / "campaigns.py"
    ).read_text(encoding="utf-8")

    assert "str(e)" not in source
