import pytest

from seo_agent.clients.dataforseo_client import DataForSEOClient, DataForSEOError


@pytest.mark.asyncio
async def test_get_search_volume_does_not_send_location(monkeypatch):
    client = DataForSEOClient(api_credentials="dummy")

    calls: list[dict] = []

    async def fake_post_json(endpoint: str, *, operation: str, **kwargs):
        calls.append({"endpoint": endpoint, "operation": operation, "kwargs": kwargs})
        # Single call should succeed and include a result payload.
        return {
            "status_code": 20000,
            "status_message": "Ok.",
            "tasks_error": 0,
            "tasks": [
                {
                    "status_code": 20000,
                    "status_message": "Ok.",
                    "result": [
                        {
                            "keyword": "best resume format 2026",
                            "search_volume": 1234,
                            "cpc": 1.23,
                            "competition": 0.4,
                            "competition_level": "MEDIUM",
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(client, "_post_json", fake_post_json)

    result = await client.get_search_volume(
        keywords=["best resume format 2026"],
        location_code=1702,  # Singapore in this repo's mapping
        language_code="en",
    )

    assert result["best resume format 2026"]["search_volume"] == 1234
    assert len(calls) == 1

    payload = calls[0]["kwargs"]["json"][0]
    assert "location_code" not in payload
    assert "location_name" not in payload
    assert payload["language_code"] == "en"


@pytest.mark.asyncio
async def test_labs_endpoints_do_not_send_location_code(monkeypatch):
    client = DataForSEOClient(api_credentials="dummy")
    calls: list[dict] = []

    async def fake_post_json(endpoint: str, *, operation: str, **kwargs):
        calls.append({"endpoint": endpoint, "operation": operation, "kwargs": kwargs})
        return {
            "status_code": 20000,
            "status_message": "Ok.",
            "tasks_error": 0,
            "tasks": [{"status_code": 20000, "status_message": "Ok.", "result": [{"items": []}]}],
        }

    monkeypatch.setattr(client, "_post_json", fake_post_json)

    await client.get_keyword_ideas(["foo"])
    await client.get_bulk_keyword_difficulty(["foo"])
    await client.get_keyword_suggestions("foo")

    assert len(calls) == 3
    for call in calls:
        payload = call["kwargs"]["json"][0]
        assert "location_code" not in payload
        assert "location_name" not in payload


@pytest.mark.asyncio
async def test_bulk_keyword_difficulty_gracefully_handles_invalid_location_field(monkeypatch):
    client = DataForSEOClient(api_credentials="dummy")

    async def fake_post_json(endpoint: str, *, operation: str, **kwargs):
        _ = endpoint, kwargs
        raise DataForSEOError(
            "DataForSEO API error during get_bulk_keyword_difficulty: status_code=20000 status_message=Ok. "
            "task_status_code=40501 task_status_message=Invalid Field: 'location_name'.",
            operation=operation,
            status_code=20000,
            status_message="Ok.",
            task_errors=[{"status_code": 40501, "status_message": "Invalid Field: 'location_name'."}],
        )

    monkeypatch.setattr(client, "_post_json", fake_post_json)

    # Should not raise; should return empty map.
    result = await client.get_bulk_keyword_difficulty(["foo"], language_code="en")
    assert result == {}

