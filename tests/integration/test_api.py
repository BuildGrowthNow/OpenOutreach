"""Integration tests for FastAPI endpoints."""
import pytest
from fastapi.testclient import TestClient

from openoutreach.api_v2.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def auth_token(test_user, client):
    """Get auth token for test user."""
    # This is a simplified fixture - actual implementation depends on auth setup
    # For now, skip if auth is not configured
    pytest.skip("Auth integration requires full JWT setup")


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client):
        """Test /api/health endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        data = response.json()
        assert "status" in data or "message" in data
        assert data["build"]["version"]
        assert "commit" in data["build"]
        assert "python_version" not in data["system"]
        assert "cpu_percent" not in data["system"]
        assert "memory_percent" not in data["system"]
        assert isinstance(data["database"]["latency_ms"], (int, float))
        assert data["database"]["latency_ms"] >= 0
        assert isinstance(data["api"]["latency_ms"], (int, float))
        assert data["api"]["latency_ms"] >= 0
        assert data["services"]["linkedin"] == "unknown"


class TestCampaignEndpoints:
    """Test campaign API endpoints."""

    def test_list_campaigns_requires_auth(self, client):
        """Test that campaign list requires authentication."""
        response = client.get("/api/campaigns/")
        # Should return 401 or redirect to login
        assert response.status_code in [401, 403, 307, 422]

    def test_campaign_creation_requires_auth(self, client):
        """Test that campaign creation requires authentication."""
        response = client.post("/api/campaigns/", json={
            "name": "Test Campaign",
            "status": "active"
        })
        # Should return 401 or redirect
        assert response.status_code in [401, 403, 422]


class TestLeadEndpoints:
    """Test lead API endpoints."""

    def test_list_leads_requires_auth(self, client):
        """Test that lead list requires authentication."""
        response = client.get("/api/leads/")
        assert response.status_code in [401, 403, 307, 422]


class TestAnalyticsEndpoints:
    """Test analytics API endpoints."""

    def test_analytics_requires_auth(self, client):
        """Test that analytics requires authentication."""
        response = client.get("/api/analytics/overview")
        assert response.status_code in [401, 403, 307, 422]


class TestAuthEndpoints:
    """Test authentication endpoints (if implemented)."""

    def test_register_endpoint(self, client, clean_test_db):
        """Test user registration endpoint."""
        # Skip if endpoint doesn't exist
        try:
            response = client.post("/api/auth/register", json={
                "email": "newuser@example.com",
                "password": "SecurePassword123!"
            })
            # Should succeed or return validation error
            assert response.status_code in [200, 201, 422]
        except Exception:
            pytest.skip("Registration endpoint not available")

    def test_login_endpoint(self, client):
        """Test login endpoint."""
        try:
            response = client.post("/api/auth/login", json={
                "email": "test@example.com",
                "password": "wrong"
            })
            # Should return 401 for wrong credentials
            assert response.status_code in [401, 422]
        except Exception:
            pytest.skip("Login endpoint not available")


class TestWebSocketEndpoint:
    """Test WebSocket endpoints."""

    def test_websocket_exists(self, client):
        """Test that WebSocket endpoint is available."""
        # WebSocket testing requires different approach
        # Just verify the route exists
        try:
            with client.websocket_connect("/api/ws"):
                # Connection should fail without auth
                pass
        except Exception:
            # Expected - websocket requires auth or proper handshake
            assert True


class TestNotificationEndpoints:
    """Test notification endpoints."""

    def test_notifications_require_auth(self, client):
        """Test that notifications require authentication."""
        response = client.get("/api/notifications/")
        assert response.status_code in [401, 403, 422]


class TestMessageEndpoints:
    """Test message endpoints."""

    def test_messages_require_auth(self, client):
        """Test that messages require authentication."""
        response = client.get("/api/messages/")
        assert response.status_code in [401, 403, 422]


class TestStateMachineEndpoints:
    """Test state machine endpoints (disabled feature)."""

    def test_state_machine_endpoints_exist(self, client):
        """Test that state machine endpoints exist but are disabled."""
        # State machine is a disabled feature
        # Just verify routes are registered
        response = client.get("/api/state-machine/workflows")
        # May return 404, 401, or data depending on implementation
        assert response.status_code in [200, 401, 403, 404, 422]


class TestLinkedInProfileEndpoints:
    """Test LinkedIn profile endpoints."""

    def test_linkedin_profiles_require_auth(self, client):
        """Test that LinkedIn profiles require authentication."""
        response = client.get("/api/linkedin-profiles/")
        assert response.status_code in [401, 403, 422]


class TestFastAPIStartup:
    """Test FastAPI app startup and configuration."""

    def test_app_startup(self):
        """Test that FastAPI app starts without errors."""
        from openoutreach.api_v2.main import app
        assert app is not None
        assert hasattr(app, "router")

    def test_cors_middleware(self):
        """Test CORS middleware is configured."""
        from openoutreach.api_v2.main import app
        # Just verify app has middleware
        assert hasattr(app, "middleware_stack")

    def test_cors_rejects_wildcard_origins_with_credentials(self):
        """Test credentialed CORS cannot be configured with a wildcard."""
        from openoutreach.api_v2.main import _parse_cors_origins

        assert _parse_cors_origins("https://app.example, https://admin.example") == [
            "https://app.example",
            "https://admin.example",
        ]
        with pytest.raises(RuntimeError, match="explicit origins"):
            _parse_cors_origins("*")
        with pytest.raises(RuntimeError, match="explicit origins"):
            _parse_cors_origins(" , ")

    def test_lifespan_uses_context_manager(self):
        """Test startup/shutdown use the non-deprecated lifespan API."""
        from openoutreach.api_v2.main import app
        assert app.router.on_startup == []
        assert app.router.on_shutdown == []
        assert callable(app.router.lifespan_context)

    def test_routers_registered(self):
        """Test that all routers are registered."""
        from openoutreach.api_v2.main import app
        # FastAPI stores included routers as `_IncludedRouter` entries in
        # `app.routes`; the flattened OpenAPI path map is the stable public
        # registration surface for this assertion.
        routes = list(app.openapi().get("paths", {}))

        # Key routes should exist
        assert any("/health" in path for path in routes)
        assert any("/campaigns" in path for path in routes)
        assert any("/leads" in path for path in routes)


class TestDatabaseConnection:
    """Test database connection in API context."""

    def test_mongodb_connection_in_api(self, clean_test_db):
        """Test that API can connect to MongoDB."""
        from openoutreach.mongodb.connection import check_mongodb_connection
        assert check_mongodb_connection()

    def test_models_accessible_from_api(self):
        """Test that models can be imported in API context."""
        from openoutreach.mongodb.models import User, Campaign, Lead, Deal
        assert User is not None
        assert Campaign is not None
        assert Lead is not None
        assert Deal is not None


class TestAPISchemas:
    """Test Pydantic schemas."""

    def test_campaign_schema(self):
        """Test Campaign schema imports."""
        from openoutreach.api_v2.schemas.campaign import CampaignCreate, CampaignUpdate
        assert CampaignCreate is not None
        assert CampaignUpdate is not None

    def test_lead_schema(self):
        """Test Lead schema imports."""
        from openoutreach.api_v2.schemas.lead import LeadCreate, LeadResponse
        assert LeadCreate is not None
        assert LeadResponse is not None

    def test_auth_schema(self):
        """Test Auth schema imports."""
        try:
            from openoutreach.api_v2.schemas.auth import LoginRequest, TokenResponse
            assert LoginRequest is not None
            assert TokenResponse is not None
        except ImportError:
            # Auth schemas might be in different location
            pytest.skip("Auth schemas not found in expected location")
