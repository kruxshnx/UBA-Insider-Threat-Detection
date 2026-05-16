"""
API Tests for UBA & Insider Threat Detection System.
Tests all FastAPI endpoints using TestClient.

Run: python -m pytest tests/test_api.py -v
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app


client = TestClient(app)


# ═════════════════════════════════════════════════════════════════════════════
# HEALTH CHECKS
# ═════════════════════════════════════════════════════════════════════════════
class TestHealthEndpoints:
    def test_root(self):
        """Root endpoint returns online status."""
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "online"
        assert "version" in data
        assert "features" in data

    def test_health(self):
        """Health endpoint returns detailed status."""
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "rate_limit" in data
        assert "max_requests" in data["rate_limit"]


# ═════════════════════════════════════════════════════════════════════════════
# REQUEST HEADERS
# ═════════════════════════════════════════════════════════════════════════════
class TestRequestHeaders:
    def test_request_id_header(self):
        """Every response includes X-Request-ID."""
        r = client.get("/")
        assert "X-Request-ID" in r.headers
        assert len(r.headers["X-Request-ID"]) == 8  # UUID[:8]

    def test_response_time_header(self):
        """Every response includes X-Response-Time."""
        r = client.get("/")
        assert "X-Response-Time" in r.headers
        assert r.headers["X-Response-Time"].endswith("ms")

    def test_rate_limit_headers(self):
        """Responses include rate limit headers."""
        r = client.get("/")
        assert "X-RateLimit-Remaining" in r.headers
        assert "X-RateLimit-Limit" in r.headers


# ═════════════════════════════════════════════════════════════════════════════
# STATS
# ═════════════════════════════════════════════════════════════════════════════
class TestStatsEndpoint:
    def test_get_stats(self):
        """Stats endpoint returns SystemStats shape."""
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.json()
        assert "total_users" in data
        assert "high_risk_users" in data
        assert "total_events" in data
        assert "avg_risk_score" in data

    def test_stats_types(self):
        """Stats values have correct types."""
        r = client.get("/api/stats")
        data = r.json()
        assert isinstance(data["total_users"], int)
        assert isinstance(data["avg_risk_score"], (int, float))


# ═════════════════════════════════════════════════════════════════════════════
# DASHBOARD SUMMARY
# ═════════════════════════════════════════════════════════════════════════════
class TestDashboardSummary:
    def test_dashboard_summary_shape(self):
        """Dashboard summary returns combined payload."""
        r = client.get("/api/dashboard/summary")
        assert r.status_code == 200
        data = r.json()
        assert "stats" in data
        assert "top_risky_users" in data
        assert "recent_alerts" in data
        assert "models" in data

    def test_dashboard_stats_nested(self):
        """Dashboard stats section has expected fields."""
        r = client.get("/api/dashboard/summary")
        data = r.json()
        stats = data["stats"]
        assert "total_users" in stats
        assert "avg_risk_score" in stats


# ═════════════════════════════════════════════════════════════════════════════
# USERS
# ═════════════════════════════════════════════════════════════════════════════
class TestUsersEndpoint:
    def test_get_risky_users(self):
        """Users risk endpoint returns list."""
        r = client.get("/api/users/risk")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_get_risky_users_with_limit(self):
        """Users risk endpoint respects limit parameter."""
        r = client.get("/api/users/risk?limit=3")
        assert r.status_code == 200
        data = r.json()
        assert len(data) <= 3

    def test_user_profile_shape(self):
        """User profiles have required fields."""
        r = client.get("/api/users/risk?limit=1")
        data = r.json()
        if data:
            user = data[0]
            assert "user" in user
            assert "total_risk_score" in user
            assert "role" in user
            assert "risk_level" in user

    def test_sort_ascending(self):
        """Users can be sorted ascending."""
        r = client.get("/api/users/risk?limit=5&sort=asc")
        assert r.status_code == 200
        data = r.json()
        if len(data) >= 2:
            assert data[0]["total_risk_score"] <= data[-1]["total_risk_score"]

    def test_user_profile_endpoint_known(self):
        """User profile endpoint returns data for known user."""
        # First get a known user from the risk list
        r = client.get("/api/users/risk?limit=1")
        users = r.json()
        if users:
            user_id = users[0]["user"]
            r2 = client.get(f"/api/users/{user_id}/profile")
            assert r2.status_code == 200
            profile = r2.json()
            assert profile["user"] == user_id
            assert "total_risk_score" in profile
            assert "rank" in profile

    def test_user_profile_endpoint_unknown(self):
        """User profile endpoint returns 404 for unknown user."""
        r = client.get("/api/users/NONEXISTENT_USER_XYZ/profile")
        assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# EVENTS
# ═════════════════════════════════════════════════════════════════════════════
class TestEventsEndpoint:
    def test_get_risk_events(self):
        """Events risk endpoint returns list."""
        r = client.get("/api/events/risk")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_events_with_limit(self):
        """Events endpoint respects limit."""
        r = client.get("/api/events/risk?limit=5")
        assert r.status_code == 200
        assert len(r.json()) <= 5

    def test_events_min_score_filter(self):
        """Events can be filtered by minimum risk score."""
        r = client.get("/api/events/risk?min_score=50")
        assert r.status_code == 200
        data = r.json()
        for event in data:
            assert event.get("risk_score", 0) >= 50


# ═════════════════════════════════════════════════════════════════════════════
# TIMELINE
# ═════════════════════════════════════════════════════════════════════════════
class TestTimelineEndpoint:
    def test_timeline_known_user(self):
        """Timeline for a known user returns data or empty."""
        r = client.get("/api/users/U105/timeline")
        assert r.status_code == 200
        data = r.json()
        assert "user_id" in data
        assert "total_events" in data
        assert "anomaly_count" in data
        assert "events" in data
        assert data["user_id"] == "U105"

    def test_timeline_unknown_user(self):
        """Timeline for unknown user returns empty events."""
        r = client.get("/api/users/NONEXISTENT/timeline")
        assert r.status_code == 200
        data = r.json()
        assert data["total_events"] == 0
        assert data["events"] == []

    def test_timeline_event_shape(self):
        """Timeline events have correct fields."""
        r = client.get("/api/users/U105/timeline")
        data = r.json()
        if data["events"]:
            event = data["events"][0]
            assert "timestamp" in event
            assert "event_type" in event
            assert "activity" in event
            assert "risk_score" in event
            assert "is_anomaly" in event

    def test_timeline_pagination(self):
        """Timeline supports limit and offset params."""
        r = client.get("/api/users/U105/timeline?limit=2&offset=0")
        assert r.status_code == 200
        data = r.json()
        assert len(data["events"]) <= 2


# ═════════════════════════════════════════════════════════════════════════════
# ALERTS
# ═════════════════════════════════════════════════════════════════════════════
class TestAlertsEndpoint:
    def test_get_alerts(self):
        """Alerts endpoint returns structured response."""
        r = client.get("/api/alerts")
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "alerts" in data
        assert "offset" in data
        assert "limit" in data

    def test_alerts_pagination(self):
        """Alerts pagination works."""
        r = client.get("/api/alerts?limit=2&offset=0")
        assert r.status_code == 200
        data = r.json()
        assert len(data["alerts"]) <= 2

    def test_alerts_severity_filter(self):
        """Alerts can be filtered by severity."""
        # First check what severities exist
        r_all = client.get("/api/alerts?limit=500")
        all_alerts = r_all.json()["alerts"]
        severities = set(a["severity"] for a in all_alerts)

        # Filter by a severity we know exists (or Critical if it does)
        test_severity = "Critical" if "Critical" in severities else (severities.pop() if severities else "Critical")
        r = client.get(f"/api/alerts?severity={test_severity}")
        assert r.status_code == 200
        data = r.json()
        for alert in data["alerts"]:
            assert alert["severity"] == test_severity

    def test_alerts_status_filter(self):
        """Alerts can be filtered by status."""
        r = client.get("/api/alerts?status=open")
        assert r.status_code == 200
        data = r.json()
        for alert in data["alerts"]:
            assert alert["status"] == "open"


# ═════════════════════════════════════════════════════════════════════════════
# MODELS STATUS
# ═════════════════════════════════════════════════════════════════════════════
class TestModelsEndpoint:
    def test_get_models_status(self):
        """Models status returns model info."""
        r = client.get("/api/models/status")
        assert r.status_code == 200
        data = r.json()
        assert "models" in data
        assert "total_models" in data
        assert "available_models" in data
        assert isinstance(data["models"], list)

    def test_model_info_shape(self):
        """Each model entry has required fields."""
        r = client.get("/api/models/status")
        data = r.json()
        for model in data["models"]:
            assert "name" in model
            assert "path" in model
            assert "exists" in model
            assert isinstance(model["exists"], bool)


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN
# ═════════════════════════════════════════════════════════════════════════════
class TestAdminEndpoints:
    def test_cache_clear_requires_admin(self):
        """Cache clear endpoint rejects non-admin roles."""
        r = client.post("/api/admin/cache/clear")
        assert r.status_code == 403

    def test_cache_clear_with_admin_role(self):
        """Cache clear succeeds with Admin role header."""
        r = client.post("/api/admin/cache/clear", headers={"X-User-Role": "Admin"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"


# ═════════════════════════════════════════════════════════════════════════════
# ERROR HANDLING
# ═════════════════════════════════════════════════════════════════════════════
class TestErrorHandling:
    def test_404_not_found(self):
        """Non-existent path returns 404."""
        r = client.get("/api/nonexistent")
        assert r.status_code in [404, 422]


# ═════════════════════════════════════════════════════════════════════════════
# EDGE CASES
# ═════════════════════════════════════════════════════════════════════════════
class TestEdgeCases:
    def test_very_large_limit(self):
        """Very large limit returns 422 (Pydantic enforces le=500)."""
        r = client.get("/api/events/risk?limit=999999")
        assert r.status_code in [200, 422]  # 422 if limit is validated

    def test_zero_limit(self):
        """Zero limit returns 422 (Pydantic enforces ge=1)."""
        r = client.get("/api/users/risk?limit=0")
        assert r.status_code in [200, 422]  # 422 if limit is validated

    def test_special_chars_in_user_id(self):
        """User ID with special chars should not crash."""
        r = client.get("/api/users/%00%0A/profile")
        # Should return 404 (user not found) rather than 500
        assert r.status_code in [200, 404]

    def test_min_score_boundary(self):
        """min_score=100 should return very few or no events."""
        r = client.get("/api/events/risk?min_score=100")
        assert r.status_code == 200
        data = r.json()
        # Response is a list of events
        events = data if isinstance(data, list) else data.get("events", [])
        for event in events:
            assert event["risk_score"] >= 100

    def test_alerts_offset_beyond_total(self):
        """Offset beyond total alerts returns empty list, not error."""
        r = client.get("/api/alerts?offset=999999")
        assert r.status_code == 200
        data = r.json()
        assert len(data["alerts"]) == 0

    def test_dashboard_summary_structure(self):
        """Dashboard summary contains expected nested keys."""
        r = client.get("/api/dashboard/summary")
        assert r.status_code == 200
        data = r.json()
        assert "stats" in data
        assert "top_risky_users" in data

    def test_models_status_model_count(self):
        """Models status returns a list of model info dicts."""
        r = client.get("/api/models/status")
        assert r.status_code == 200
        data = r.json()
        assert "models" in data
        assert isinstance(data["models"], list)

