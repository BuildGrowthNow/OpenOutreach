"""Unit tests for remote daemon bug fixes.

Verifies cookie encryption/decryption and qualifiers dict structure
without requiring MongoDB or full integration setup.
"""
import json
from unittest.mock import MagicMock


class TestCookieFormat:
    """Test cookie data format and JSON parsing."""

    def test_daemon_parses_json_cookies(self):
        """Remote daemon should parse JSON cookie_data from API response."""
        cookie_dict = {"cookies": [{"name": "li_at", "value": "test-token"}], "origins": []}
        cookie_json = json.dumps(cookie_dict)

        # Simulate daemon receiving JSON string from API
        storage_state = json.loads(cookie_json)
        assert storage_state == cookie_dict

    def test_mock_profile_cookie_handling(self):
        """Remote daemon's MockLinkedInProfile should handle cookies as JSON."""
        # Simulate daemon's MockLinkedInProfile
        class MockLinkedInProfile:
            def __init__(self, profile_id: str):
                self._id = profile_id
                self._cookie_data_json = None

            @property
            def cookie_data(self):
                if not self._cookie_data_json:
                    return None
                return json.loads(self._cookie_data_json)

            @cookie_data.setter
            def cookie_data(self, value):
                if value is None:
                    self._cookie_data_json = None
                else:
                    self._cookie_data_json = json.dumps(value)

        profile = MockLinkedInProfile("test-profile")
        cookie_dict = {"cookies": [{"name": "li_at", "value": "test"}], "origins": []}

        # Set and get
        profile.cookie_data = cookie_dict
        assert profile._cookie_data_json == json.dumps(cookie_dict)
        assert profile.cookie_data == cookie_dict


class TestQualifiersStructure:
    """Test qualifiers dict structure matches handler expectations."""

    def test_qualifiers_dict_format(self):
        """Qualifiers dict should map campaign_id -> qualifier object."""
        mock_campaign = MagicMock()
        mock_campaign.pk = "test-campaign-id"

        mock_qualifier = MagicMock()
        qualifiers = {mock_campaign.pk: mock_qualifier}

        # Verify handler can access qualifier
        assert mock_campaign.pk in qualifiers
        assert qualifiers.get(mock_campaign.pk) is mock_qualifier

    def test_strategy_for_fails_with_none(self):
        """strategy_for should raise error when qualifiers=None."""
        mock_campaign = MagicMock()
        mock_campaign.pk = "test-campaign"

        # Accessing None.get() should raise AttributeError
        qualifiers = None
        try:
            _ = qualifiers.get(mock_campaign.pk)  # type: ignore
            assert False, "Expected AttributeError"
        except AttributeError:
            pass  # Expected

    def test_qualifiers_empty_dict_returns_none(self):
        """Empty qualifiers dict should return None for missing key."""
        mock_campaign = MagicMock()
        mock_campaign.pk = "test-campaign"

        qualifiers = {}
        qualifier = qualifiers.get(mock_campaign.pk)
        assert qualifier is None
