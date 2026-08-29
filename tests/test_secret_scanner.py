from scripts.scan_secrets import scan_text


def test_scanner_detects_private_key_without_returning_secret():
    findings = scan_text("-----BEGIN PRIVATE KEY-----\nsecret material\n-----END PRIVATE KEY-----")
    assert findings == ["private-key"]


def test_scanner_detects_credentialed_database_url():
    findings = scan_text("MONGO=mongodb+srv://user:password@example.test/db")
    assert findings == ["credentialed-database-url"]


def test_scanner_detects_high_confidence_provider_tokens():
    findings = scan_text("token=ghp_123456789012345678901234567890")
    assert findings == ["github-token"]


def test_scanner_allows_environment_references_and_placeholders():
    assert scan_text('API_KEY = os.environ["API_KEY"]') == []
    assert scan_text('API_KEY = "${API_KEY}"') == []
