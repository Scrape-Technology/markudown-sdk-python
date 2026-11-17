import httpx
import pytest

from markudown import AsyncMarkUDown, JobFailedError, MarkUDown, MarkUDownError


def _transport(status_body: dict, status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"success": True, "id": "j1", "url": "/api/crawl/j1"})
        return httpx.Response(status_code, json=status_body)
    return httpx.MockTransport(handler)


def _client(transport: httpx.MockTransport) -> MarkUDown:
    md = MarkUDown(api_key="k", poll_interval=0, poll_timeout=5)
    md._http = httpx.Client(base_url="http://test", transport=transport)
    return md


def test_not_found_status_stops_polling():
    md = _client(_transport({"success": False, "id": "j1", "status": "not_found"}))
    with pytest.raises(MarkUDownError) as exc:
        md.crawl("https://example.com")
    assert exc.value.status_code == 404


def test_http_404_stops_polling():
    md = _client(_transport({"detail": "Job not found"}, status_code=404))
    with pytest.raises(MarkUDownError) as exc:
        md.crawl("https://example.com")
    assert exc.value.status_code == 404


def test_failed_status_raises_job_failed():
    md = _client(_transport({"success": False, "id": "j1", "status": "failed", "error": "boom"}))
    with pytest.raises(JobFailedError):
        md.crawl("https://example.com")


def test_async_not_found_status_stops_polling():
    import asyncio

    async def run():
        md = AsyncMarkUDown(api_key="k", poll_interval=0, poll_timeout=5)
        md._http = httpx.AsyncClient(
            base_url="http://test", transport=_transport({"success": False, "id": "j1", "status": "not_found"})
        )
        with pytest.raises(MarkUDownError) as exc:
            await md.crawl("https://example.com")
        assert exc.value.status_code == 404

    asyncio.run(run())
