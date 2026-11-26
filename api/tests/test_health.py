from unittest.mock import patch


def test_health_ok(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"
    assert body["database"] == "ok"
    assert body["version"]


def test_health_reports_database_unavailable(client):
    with patch("app.routers.health.check_database", return_value=False):
        res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["database"] == "unavailable"


def test_cors_allows_configured_origin(client):
    res = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
