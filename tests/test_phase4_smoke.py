from app import app


def test_daily_report_endpoint_returns_summary():
    client = app.test_client()
    response = client.get("/api/report/daily")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["report_type"] == "daily"
    assert "summary" in payload
    assert "trade_count" in payload["summary"]
