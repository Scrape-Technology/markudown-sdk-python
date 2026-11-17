"""MarkUDown Python SDK — https://scrapetechnology.com/markudown"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Literal, Optional

import httpx

DEFAULT_BASE_URL = "https://api.scrapetechnology.com"
DEFAULT_TIMEOUT = 120
DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_POLL_TIMEOUT = 300.0


# ── Exceptions ────────────────────────────────────────────────────────────────


class MarkUDownError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(MarkUDownError):
    pass


class InsufficientCreditsError(MarkUDownError):
    pass


class JobFailedError(MarkUDownError):
    pass


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    try:
        detail = resp.json().get("detail", f"HTTP {resp.status_code}")
    except Exception:
        detail = f"HTTP {resp.status_code}"
    if resp.status_code == 429:
        raise RateLimitError(detail, 429)
    if resp.status_code in (402, 403):
        raise InsufficientCreditsError(detail, resp.status_code)
    raise MarkUDownError(detail, resp.status_code)


# ── Sync client ───────────────────────────────────────────────────────────────


class MarkUDown:
    """Synchronous MarkUDown client.

    Usage::

        from markudown import MarkUDown

        md = MarkUDown(api_key="your-key")
        result = md.scrape("https://example.com")
        print(result["markdown"])
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        poll_timeout: float = DEFAULT_POLL_TIMEOUT,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self._http = httpx.Client(
            base_url=self.base_url,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "MarkUDown":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _post(self, path: str, body: dict) -> dict:
        resp = self._http.post(f"/api{path}", json=body)
        _raise_for_status(resp)
        return resp.json()

    def _get(self, path: str) -> dict:
        resp = self._http.get(f"/api{path}")
        _raise_for_status(resp)
        return resp.json()

    def _delete(self, path: str) -> dict:
        resp = self._http.delete(f"/api{path}")
        _raise_for_status(resp)
        return resp.json()

    def _poll(self, queue: str, job_id: str) -> dict:
        deadline = time.monotonic() + self.poll_timeout
        while time.monotonic() < deadline:
            data = self._get(f"/{queue}/{job_id}")
            status = data.get("status")
            if status == "completed":
                return data
            if status == "failed":
                raise JobFailedError(data.get("error", "Job failed"))
            if status == "not_found":
                # expired from the queue or wrong id — it will never complete
                raise MarkUDownError(f"Job {job_id} not found", 404)
            time.sleep(self.poll_interval)
        raise MarkUDownError(f"Polling timed out after {self.poll_timeout}s")

    def _submit(self, queue: str, body: dict, wait: bool) -> dict:
        resp = self._post(f"/{queue}", body)
        if not wait:
            return resp
        return self._poll(queue, resp["id"])

    # ── Scrape (sync) ─────────────────────────────────────────────────────────

    def scrape(
        self,
        url: str,
        *,
        timeout: int = 60,
        exclude_tags: Optional[list[str]] = None,
        main_content: bool = True,
        include_links: bool = False,
        include_html: bool = False,
    ) -> dict:
        """Scrape a single URL. Returns result immediately.

        Args:
            url: URL to scrape.
            timeout: Request timeout in seconds.
            exclude_tags: HTML tags to exclude (default: header, nav, footer).
            main_content: Extract only main content area.
            include_links: Include hyperlinks in the output.
            include_html: Include raw HTML in the output.
        """
        return self._post("/scrape", {
            "url": [url],
            "timeout": timeout,
            "main_content": main_content,
            "include_link": include_links,
            "include_html": include_html,
            "exclude_tags": exclude_tags or ["header", "nav", "footer"],
        })

    def screenshot(self, url: str, *, timeout: int = 60) -> dict:
        """Take a screenshot of a URL. Returns result immediately."""
        return self._post("/screenshot", {"url": [url], "timeout": timeout})

    # ── Map ───────────────────────────────────────────────────────────────────

    def map(
        self,
        url: str,
        *,
        allowed_words: Optional[list[str]] = None,
        blocked_words: Optional[list[str]] = None,
        max_urls: int = 1000,
        wait: bool = True,
    ) -> dict:
        """Discover all URLs on a website.

        Args:
            url: Root URL to map.
            allowed_words: Only include URLs containing these keywords.
            blocked_words: Exclude URLs containing these keywords.
            max_urls: Maximum number of URLs to return.
            wait: If True, poll until the job completes.
        """
        return self._submit("map", {
            "url": [url],
            "max_urls": max_urls,
            "allowed_words": allowed_words or [],
            "blocked_words": blocked_words or [],
        }, wait)

    # ── Crawl ─────────────────────────────────────────────────────────────────

    def crawl(
        self,
        url: str,
        *,
        max_depth: int = 2,
        limit: int = 10,
        timeout: int = 60,
        include_links: bool = False,
        include_html: bool = False,
        exclude_tags: Optional[list[str]] = None,
        blocked_words: Optional[list[str]] = None,
        include_only: Optional[list[str]] = None,
        main_content: bool = True,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Crawl a website recursively.

        Args:
            url: Starting URL.
            max_depth: Maximum crawl depth.
            limit: Maximum number of pages to crawl.
            timeout: Per-page timeout in seconds.
            include_links: Add each page's links to its result (``links``).
            include_html: Include raw HTML in output.
            exclude_tags: HTML tags to strip.
            blocked_words: Skip URLs containing these words.
            include_only: Only follow URLs containing one of these strings
                (``*`` matches anything, e.g. "/blog/*/2024"). The start URL is always crawled.
            main_content: Extract only main content area.
            callback_url: Webhook URL to notify when the job completes.
            wait: If True, poll until the job completes.
        """
        body: dict = {
            "url": [url],
            "max_depth": max_depth,
            "limit": limit,
            "timeout": timeout,
            "include_link": include_links,
            "include_html": include_html,
            "exclude_tags": exclude_tags or [],
            "blocked_words": blocked_words or [],
            "include_only": include_only or [],
            "main_content": main_content,
        }
        if callback_url:
            body["callback_url"] = callback_url
        return self._submit("crawl", body, wait)

    # ── Extract ───────────────────────────────────────────────────────────────

    def extract(
        self,
        url: str,
        schema: list[dict],
        *,
        extract_query: str = "",
        extraction_scope: Optional[str] = None,
        extraction_target: Optional[str] = None,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Schema-based structured data extraction.

        Args:
            url: URL to extract data from.
            schema: List of field definitions: [{"name": "price", "type": "float", "active": True}].
            extract_query: Natural language description of what to extract.
            extraction_scope: Hint for the LLM, e.g. "single_page" or "list_page".
                Extract only ever reads the page at ``url``.
            extraction_target: Hint for the LLM, e.g. a category name.
            callback_url: Webhook URL to notify on completion.
            wait: If True, poll until the job completes.
        """
        body: dict = {
            "url": url,
            "schema": schema,
            "extract_query": extract_query,
        }
        if extraction_scope:
            body["extraction_scope"] = extraction_scope
        if extraction_target:
            body["extraction_target"] = extraction_target
        if callback_url:
            body["callback_url"] = callback_url
        return self._submit("extract", body, wait)

    def prompt_extract(
        self,
        url: str,
        prompt: str,
        *,
        timeout: int = 60,
        main_content: bool = True,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Extract data using a natural language prompt (no schema needed).

        Args:
            url: URL to extract from.
            prompt: Natural language description of what to extract.
            timeout: Request timeout in seconds.
            main_content: Extract only main content area.
            callback_url: Webhook URL to notify on completion.
            wait: If True, poll until the job completes.
        """
        body: dict = {"url": url, "prompt": prompt, "timeout": timeout, "main_content": main_content}
        if callback_url:
            body["callback_url"] = callback_url
        resp = self._post("/prompt-extract", body)
        if not wait:
            return resp
        return self._poll("extract", resp["id"])

    def create_schema(self, query: str) -> dict:
        """Generate an extraction schema from a natural language query.

        Args:
            query: Natural language description of the data to extract.

        Returns:
            A schema dict ready to pass to ``extract()``.
        """
        return self._post("/create-schema", {"query": query})

    # ── Batch scrape ──────────────────────────────────────────────────────────

    def batch_scrape(
        self,
        urls: list[str],
        *,
        timeout: int = 60,
        exclude_tags: Optional[list[str]] = None,
        main_content: bool = True,
        include_links: bool = False,
        include_html: bool = False,
        wait: bool = True,
    ) -> dict:
        """Scrape multiple URLs in parallel.

        Args:
            urls: List of URLs to scrape.
            timeout: Per-URL timeout in seconds.
            exclude_tags: HTML tags to strip.
            main_content: Extract only main content.
            include_links: Include hyperlinks in output.
            include_html: Include raw HTML in output.
            wait: If True, poll until the job completes.
        """
        return self._submit("batch-scrape", {
            "url": urls,
            "timeout": timeout,
            "main_content": main_content,
            "include_link": include_links,
            "include_html": include_html,
            "exclude_tags": exclude_tags or [],
        }, wait)

    # ── Search ────────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        scrape_results: bool = True,
        lang: str = "en",
        country: str = "us",
        timeout: int = 60,
        engine: Literal["google", "bing", "duckduckgo", "all"] = "google",
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Web search + optional scraping of results.

        Args:
            query: Search query string.
            limit: Maximum number of results.
            scrape_results: Whether to scrape each result page.
            lang: Language code (e.g. "en", "pt").
            country: Country code (e.g. "us", "br").
            timeout: Request timeout in seconds.
            engine: Search engine to use.
            callback_url: Webhook URL to notify on completion.
            wait: If True, poll until the job completes.
        """
        body: dict = {
            "query": query,
            "limit": limit,
            "scrape_results": scrape_results,
            "lang": lang,
            "country": country,
            "timeout": timeout,
            "engine": engine,
        }
        if callback_url:
            body["callback_url"] = callback_url
        return self._submit("search", body, wait)

    # ── RSS ───────────────────────────────────────────────────────────────────

    def rss(
        self,
        url: str,
        *,
        max_items: int = 20,
        title: Optional[str] = None,
        timeout: int = 60,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Generate an RSS feed from a web page.

        Args:
            url: URL of the page to generate RSS from.
            max_items: Maximum number of feed items.
            title: Custom feed title (defaults to the page title).
            timeout: Request timeout in seconds.
            callback_url: Webhook URL to notify on completion.
            wait: If True, poll until the job completes.
        """
        body: dict = {"url": url, "max_items": max_items, "timeout": timeout}
        if title:
            body["title"] = title
        if callback_url:
            body["callback_url"] = callback_url
        return self._submit("rss", body, wait)

    # ── Change Detection ──────────────────────────────────────────────────────

    def change_detection(
        self,
        url: str,
        *,
        main_content: bool = True,
        include_diff: bool = True,
        timeout: int = 60,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Detect content changes on a page.

        Args:
            url: URL to check for changes.
            main_content: Compare only main content area.
            include_diff: Include a diff of changed sections.
            timeout: Request timeout in seconds.
            callback_url: Webhook URL to notify on completion.
            wait: If True, poll until the job completes.
        """
        body: dict = {
            "url": url,
            "main_content": main_content,
            "include_diff": include_diff,
            "timeout": timeout,
        }
        if callback_url:
            body["callback_url"] = callback_url
        return self._submit("change-detection", body, wait)

    # ── Deep Research ─────────────────────────────────────────────────────────

    def deep_research(
        self,
        query: str,
        urls: list[str],
        *,
        max_tokens: int = 4096,
        timeout: int = 180,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Scrape multiple pages and synthesize findings with an LLM.

        Args:
            query: Research question or topic.
            urls: List of URLs to scrape and synthesize.
            max_tokens: Maximum tokens in the LLM response.
            timeout: Request timeout in seconds.
            callback_url: Webhook URL to notify on completion.
            wait: If True, poll until the job completes.
        """
        body: dict = {"query": query, "urls": urls, "max_tokens": max_tokens, "timeout": timeout}
        if callback_url:
            body["callback_url"] = callback_url
        return self._submit("deep-research", body, wait)

    # ── Agent ─────────────────────────────────────────────────────────────────

    def agent(
        self,
        url: str,
        prompt: str,
        *,
        max_steps: int = 10,
        max_pages: int = 5,
        allow_navigation: bool = True,
        include_screenshots: bool = False,
        timeout: int = 120,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """AI autonomous navigation agent.

        Args:
            url: Starting URL for the agent.
            prompt: Task description for the agent.
            max_steps: Maximum number of actions the agent can take.
            max_pages: Maximum number of pages to visit.
            allow_navigation: Allow the agent to follow links.
            include_screenshots: Attach a base64 PNG of each page the agent reads
                (viewport only) to that step as ``screenshot``.
            timeout: Request timeout in seconds.
            callback_url: Webhook URL to notify on completion.
            wait: If True, poll until the job completes.
        """
        body: dict = {
            "url": url,
            "prompt": prompt,
            "max_steps": max_steps,
            "max_pages": max_pages,
            "allow_navigation": allow_navigation,
            "include_screenshots": include_screenshots,
            "timeout": timeout,
        }
        if callback_url:
            body["callback_url"] = callback_url
        return self._submit("agent", body, wait)

    # ── Smart Extract ─────────────────────────────────────────────────────────

    def smart_extract(
        self,
        url: str,
        goal: str,
        *,
        hints: Optional[list[str]] = None,
        schema: Optional[dict[str, str]] = None,
        output_format: Literal["markdown", "json", "csv"] = "markdown",
        max_pages: int = 20,
        timeout: int = 60,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Guided extraction: analyzes the site, plans interactions, returns complete data.

        Args:
            url: URL to extract from.
            goal: Natural language description of what to extract.
            hints: Optional hints to guide the extraction (e.g. ["click 'Load more' to get all items"]).
            schema: Optional output schema {"field": "type"}.
            output_format: "markdown", "json" or "csv". With "json" or "csv" and a
                schema, records come back in ``json_data`` ("csv" adds them as CSV text in ``csv``).
            max_pages: Maximum pages to visit.
            timeout: Request timeout in seconds.
            callback_url: Webhook URL to notify on completion.
            wait: If True, poll until the job completes.
        """
        body: dict = {
            "url": url,
            "goal": goal,
            "hints": hints or [],
            "output_format": output_format,
            "max_pages": max_pages,
            "timeout": timeout,
        }
        if schema:
            body["schema"] = schema
        if callback_url:
            body["callback_url"] = callback_url
        return self._submit("smart-extract", body, wait)

    # ── Rank ──────────────────────────────────────────────────────────────────

    def rank(
        self,
        keyword: str,
        domain: str,
        *,
        engine: Literal["google", "bing"] = "google",
        lang: str = "en",
        country: str = "us",
        depth: int = 100,
        timeout: int = 60,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Check where a domain ranks for a keyword in search results.

        Args:
            keyword: Search keyword to check.
            domain: Domain to find in the results (e.g. "example.com").
            engine: Search engine to use.
            lang: Language code.
            country: Country code.
            depth: How many results to scan (max 100).
            timeout: Request timeout in seconds.
            callback_url: Webhook URL to notify on completion.
            wait: If True, poll until the job completes.
        """
        body: dict = {
            "keyword": keyword,
            "domain": domain,
            "engine": engine,
            "lang": lang,
            "country": country,
            "depth": depth,
            "timeout": timeout,
        }
        if callback_url:
            body["callback_url"] = callback_url
        return self._submit("rank", body, wait)

    # ── Dataset ───────────────────────────────────────────────────────────────

    def dataset(
        self,
        url: str,
        goal: str,
        *,
        schema: Optional[dict[str, str]] = None,
        max_pages: int = 10,
        output_format: Literal["json", "csv"] = "json",
        timeout: int = 180,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Auto-paginate a listing page and extract all items as a structured dataset.

        Args:
            url: URL of the listing page.
            goal: Natural language description of items to extract.
            schema: Optional output schema {"field": "type"}.
            max_pages: Maximum pages to paginate through.
            output_format: "json" or "csv". ``data`` is always the list of records;
                with "csv" the result also carries them as CSV text in ``csv``.
            timeout: Request timeout in seconds.
            callback_url: Webhook URL to notify on completion.
            wait: If True, poll until the job completes.
        """
        body: dict = {
            "url": url,
            "goal": goal,
            "max_pages": max_pages,
            "output_format": output_format,
            "timeout": timeout,
        }
        if schema:
            body["schema"] = schema
        if callback_url:
            body["callback_url"] = callback_url
        return self._submit("dataset", body, wait)

    # ── Monitor ───────────────────────────────────────────────────────────────

    def monitor_create(
        self,
        url: str,
        callback_url: str,
        *,
        interval_minutes: int = 60,
        main_content: bool = True,
        timeout: int = 60,
    ) -> dict:
        """Create a persistent URL monitor that sends a webhook when content changes.

        Args:
            url: URL to monitor.
            callback_url: Webhook URL to call when changes are detected.
            interval_minutes: How often to check for changes.
            main_content: Compare only main content area.
            timeout: Request timeout in seconds.
        """
        return self._post("/monitor", {
            "url": url,
            "callback_url": callback_url,
            "interval_minutes": interval_minutes,
            "main_content": main_content,
            "timeout": timeout,
        })

    def monitor_list(self) -> dict:
        """List all active monitor subscriptions."""
        return self._get("/monitor")

    def monitor_delete(self, subscription_id: str) -> dict:
        """Deactivate a monitor subscription.

        Args:
            subscription_id: ID returned by ``monitor_create()``.
        """
        return self._delete(f"/monitor/{subscription_id}")

    # ── Job management ────────────────────────────────────────────────────────

    def get_job_status(self, queue: str, job_id: str) -> dict:
        """Get the current status of any async job.

        Args:
            queue: Endpoint name (e.g. "crawl", "search", "extract").
            job_id: Job ID returned when the job was submitted.
        """
        return self._get(f"/{queue}/{job_id}")

    def cancel_job(self, queue: str, job_id: str) -> dict:
        """Cancel a running async job.

        Args:
            queue: Endpoint name (e.g. "crawl", "agent").
            job_id: Job ID to cancel.
        """
        return self._delete(f"/{queue}/{job_id}")


# ── Async client ──────────────────────────────────────────────────────────────


class AsyncMarkUDown:
    """Asynchronous MarkUDown client.

    Usage::

        from markudown import AsyncMarkUDown

        async with AsyncMarkUDown(api_key="your-key") as md:
            result = await md.scrape("https://example.com")
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        poll_timeout: float = DEFAULT_POLL_TIMEOUT,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "AsyncMarkUDown":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _post(self, path: str, body: dict) -> dict:
        resp = await self._http.post(f"/api{path}", json=body)
        _raise_for_status(resp)
        return resp.json()

    async def _get(self, path: str) -> dict:
        resp = await self._http.get(f"/api{path}")
        _raise_for_status(resp)
        return resp.json()

    async def _delete(self, path: str) -> dict:
        resp = await self._http.delete(f"/api{path}")
        _raise_for_status(resp)
        return resp.json()

    async def _poll(self, queue: str, job_id: str) -> dict:
        deadline = time.monotonic() + self.poll_timeout
        while time.monotonic() < deadline:
            data = await self._get(f"/{queue}/{job_id}")
            status = data.get("status")
            if status == "completed":
                return data
            if status == "failed":
                raise JobFailedError(data.get("error", "Job failed"))
            if status == "not_found":
                # expired from the queue or wrong id — it will never complete
                raise MarkUDownError(f"Job {job_id} not found", 404)
            await asyncio.sleep(self.poll_interval)
        raise MarkUDownError(f"Polling timed out after {self.poll_timeout}s")

    async def _submit(self, queue: str, body: dict, wait: bool) -> dict:
        resp = await self._post(f"/{queue}", body)
        if not wait:
            return resp
        return await self._poll(queue, resp["id"])

    # ── Scrape (sync) ─────────────────────────────────────────────────────────

    async def scrape(
        self,
        url: str,
        *,
        timeout: int = 60,
        exclude_tags: Optional[list[str]] = None,
        main_content: bool = True,
        include_links: bool = False,
        include_html: bool = False,
    ) -> dict:
        """Scrape a single URL. Returns result immediately."""
        return await self._post("/scrape", {
            "url": [url],
            "timeout": timeout,
            "main_content": main_content,
            "include_link": include_links,
            "include_html": include_html,
            "exclude_tags": exclude_tags or ["header", "nav", "footer"],
        })

    async def screenshot(self, url: str, *, timeout: int = 60) -> dict:
        """Take a screenshot of a URL. Returns result immediately."""
        return await self._post("/screenshot", {"url": [url], "timeout": timeout})

    async def map(
        self,
        url: str,
        *,
        allowed_words: Optional[list[str]] = None,
        blocked_words: Optional[list[str]] = None,
        max_urls: int = 1000,
        wait: bool = True,
    ) -> dict:
        """Discover all URLs on a website."""
        return await self._submit("map", {
            "url": [url],
            "max_urls": max_urls,
            "allowed_words": allowed_words or [],
            "blocked_words": blocked_words or [],
        }, wait)

    async def crawl(
        self,
        url: str,
        *,
        max_depth: int = 2,
        limit: int = 10,
        timeout: int = 60,
        include_links: bool = False,
        include_html: bool = False,
        exclude_tags: Optional[list[str]] = None,
        blocked_words: Optional[list[str]] = None,
        include_only: Optional[list[str]] = None,
        main_content: bool = True,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Crawl a website recursively."""
        body: dict = {
            "url": [url],
            "max_depth": max_depth,
            "limit": limit,
            "timeout": timeout,
            "include_link": include_links,
            "include_html": include_html,
            "exclude_tags": exclude_tags or [],
            "blocked_words": blocked_words or [],
            "include_only": include_only or [],
            "main_content": main_content,
        }
        if callback_url:
            body["callback_url"] = callback_url
        return await self._submit("crawl", body, wait)

    async def extract(
        self,
        url: str,
        schema: list[dict],
        *,
        extract_query: str = "",
        extraction_scope: Optional[str] = None,
        extraction_target: Optional[str] = None,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Schema-based structured data extraction."""
        body: dict = {
            "url": url,
            "schema": schema,
            "extract_query": extract_query,
        }
        if extraction_scope:
            body["extraction_scope"] = extraction_scope
        if extraction_target:
            body["extraction_target"] = extraction_target
        if callback_url:
            body["callback_url"] = callback_url
        return await self._submit("extract", body, wait)

    async def prompt_extract(
        self,
        url: str,
        prompt: str,
        *,
        timeout: int = 60,
        main_content: bool = True,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Extract data using a natural language prompt (no schema needed)."""
        body: dict = {"url": url, "prompt": prompt, "timeout": timeout, "main_content": main_content}
        if callback_url:
            body["callback_url"] = callback_url
        resp = await self._post("/prompt-extract", body)
        if not wait:
            return resp
        return await self._poll("extract", resp["id"])

    async def create_schema(self, query: str) -> dict:
        """Generate an extraction schema from a natural language query."""
        return await self._post("/create-schema", {"query": query})

    async def batch_scrape(
        self,
        urls: list[str],
        *,
        timeout: int = 60,
        exclude_tags: Optional[list[str]] = None,
        main_content: bool = True,
        include_links: bool = False,
        include_html: bool = False,
        wait: bool = True,
    ) -> dict:
        """Scrape multiple URLs in parallel."""
        return await self._submit("batch-scrape", {
            "url": urls,
            "timeout": timeout,
            "main_content": main_content,
            "include_link": include_links,
            "include_html": include_html,
            "exclude_tags": exclude_tags or [],
        }, wait)

    async def search(
        self,
        query: str,
        *,
        limit: int = 5,
        scrape_results: bool = True,
        lang: str = "en",
        country: str = "us",
        timeout: int = 60,
        engine: Literal["google", "bing", "duckduckgo", "all"] = "google",
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Web search + optional scraping of results."""
        body: dict = {
            "query": query,
            "limit": limit,
            "scrape_results": scrape_results,
            "lang": lang,
            "country": country,
            "timeout": timeout,
            "engine": engine,
        }
        if callback_url:
            body["callback_url"] = callback_url
        return await self._submit("search", body, wait)

    async def rss(
        self,
        url: str,
        *,
        max_items: int = 20,
        title: Optional[str] = None,
        timeout: int = 60,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Generate an RSS feed from a web page."""
        body: dict = {"url": url, "max_items": max_items, "timeout": timeout}
        if title:
            body["title"] = title
        if callback_url:
            body["callback_url"] = callback_url
        return await self._submit("rss", body, wait)

    async def change_detection(
        self,
        url: str,
        *,
        main_content: bool = True,
        include_diff: bool = True,
        timeout: int = 60,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Detect content changes on a page."""
        body: dict = {
            "url": url,
            "main_content": main_content,
            "include_diff": include_diff,
            "timeout": timeout,
        }
        if callback_url:
            body["callback_url"] = callback_url
        return await self._submit("change-detection", body, wait)

    async def deep_research(
        self,
        query: str,
        urls: list[str],
        *,
        max_tokens: int = 4096,
        timeout: int = 180,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Scrape multiple pages and synthesize findings with an LLM."""
        body: dict = {"query": query, "urls": urls, "max_tokens": max_tokens, "timeout": timeout}
        if callback_url:
            body["callback_url"] = callback_url
        return await self._submit("deep-research", body, wait)

    async def agent(
        self,
        url: str,
        prompt: str,
        *,
        max_steps: int = 10,
        max_pages: int = 5,
        allow_navigation: bool = True,
        include_screenshots: bool = False,
        timeout: int = 120,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """AI autonomous navigation agent."""
        body: dict = {
            "url": url,
            "prompt": prompt,
            "max_steps": max_steps,
            "max_pages": max_pages,
            "allow_navigation": allow_navigation,
            "include_screenshots": include_screenshots,
            "timeout": timeout,
        }
        if callback_url:
            body["callback_url"] = callback_url
        return await self._submit("agent", body, wait)

    async def smart_extract(
        self,
        url: str,
        goal: str,
        *,
        hints: Optional[list[str]] = None,
        schema: Optional[dict[str, str]] = None,
        output_format: Literal["markdown", "json", "csv"] = "markdown",
        max_pages: int = 20,
        timeout: int = 60,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Guided extraction: analyzes the site, plans interactions, returns complete data."""
        body: dict = {
            "url": url,
            "goal": goal,
            "hints": hints or [],
            "output_format": output_format,
            "max_pages": max_pages,
            "timeout": timeout,
        }
        if schema:
            body["schema"] = schema
        if callback_url:
            body["callback_url"] = callback_url
        return await self._submit("smart-extract", body, wait)

    async def rank(
        self,
        keyword: str,
        domain: str,
        *,
        engine: Literal["google", "bing"] = "google",
        lang: str = "en",
        country: str = "us",
        depth: int = 100,
        timeout: int = 60,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Check where a domain ranks for a keyword in search results."""
        body: dict = {
            "keyword": keyword,
            "domain": domain,
            "engine": engine,
            "lang": lang,
            "country": country,
            "depth": depth,
            "timeout": timeout,
        }
        if callback_url:
            body["callback_url"] = callback_url
        return await self._submit("rank", body, wait)

    async def dataset(
        self,
        url: str,
        goal: str,
        *,
        schema: Optional[dict[str, str]] = None,
        max_pages: int = 10,
        output_format: Literal["json", "csv"] = "json",
        timeout: int = 180,
        callback_url: Optional[str] = None,
        wait: bool = True,
    ) -> dict:
        """Auto-paginate a listing page and extract all items as a structured dataset."""
        body: dict = {
            "url": url,
            "goal": goal,
            "max_pages": max_pages,
            "output_format": output_format,
            "timeout": timeout,
        }
        if schema:
            body["schema"] = schema
        if callback_url:
            body["callback_url"] = callback_url
        return await self._submit("dataset", body, wait)

    async def monitor_create(
        self,
        url: str,
        callback_url: str,
        *,
        interval_minutes: int = 60,
        main_content: bool = True,
        timeout: int = 60,
    ) -> dict:
        """Create a persistent URL monitor that sends a webhook when content changes."""
        return await self._post("/monitor", {
            "url": url,
            "callback_url": callback_url,
            "interval_minutes": interval_minutes,
            "main_content": main_content,
            "timeout": timeout,
        })

    async def monitor_list(self) -> dict:
        """List all active monitor subscriptions."""
        return await self._get("/monitor")

    async def monitor_delete(self, subscription_id: str) -> dict:
        """Deactivate a monitor subscription."""
        return await self._delete(f"/monitor/{subscription_id}")

    async def get_job_status(self, queue: str, job_id: str) -> dict:
        """Get the current status of any async job."""
        return await self._get(f"/{queue}/{job_id}")

    async def cancel_job(self, queue: str, job_id: str) -> dict:
        """Cancel a running async job."""
        return await self._delete(f"/{queue}/{job_id}")
