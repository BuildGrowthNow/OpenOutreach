from pathlib import Path


ROUTERS = Path(__file__).parents[2] / "openoutreach" / "api_v2" / "routers"


def test_linkedin_credential_routes_do_not_return_raw_exceptions():
    source = (ROUTERS / "linkedin_credentials.py").read_text(encoding="utf-8")

    # Provider and database exception text can contain cookies, proxy credentials,
    # request URLs, or other secrets. Client-facing errors must remain generic.
    assert "str(e)" not in source
    assert "details={\"method\": \"browser_login\", \"message\": str(e)}" not in source
    assert "details={\"method\": \"browser_login\", \"error\": str(e)}" not in source
    assert 'error=str(e)' not in source


def test_linkedin_profile_routes_do_not_return_raw_exceptions():
    source = (ROUTERS / "linkedin_profiles.py").read_text(encoding="utf-8")

    # Cookie and proxy parsing failures are especially likely to echo input data.
    assert "str(e)" not in source
    assert "detail=str(exc)" not in source
    assert 'error=str(e)' not in source
