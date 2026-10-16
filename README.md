# MarkUDown Python SDK

Python SDK for [MarkUDown](https://scrapetechnology.com/markudown) — AI data extraction infrastructure that turns any website into structured, ready-to-use data.

## Installation

```bash
pip install markudown
```

## Quick Start

```python
from markudown import MarkUDown

md = MarkUDown(api_key="your-api-key")

# Scrape a page
result = md.scrape("https://example.com")
print(result["markdown"])

# Search the web
results = md.search("best web scraping tools 2025", engine="google", limit=5)

# Extract structured data
data = md.extract(
    "https://shop.example.com/products",
    schema=[
        {"name": "title",  "type": "string", "active": True},
        {"name": "price",  "type": "float",  "active": True},
        {"name": "rating", "type": "float",  "active": True},
    ],
    extract_query="Extract all product listings with title, price and rating",
)
```

Get your API key at [scrapetechnology.com/markudown](https://scrapetechnology.com/markudown). New accounts include **500 free credits**.

---

## Async Client

```python
import asyncio
from markudown import AsyncMarkUDown

async def main():
    async with AsyncMarkUDown(api_key="your-api-key") as md:
        result = await md.scrape("https://example.com")
        print(result["markdown"])

asyncio.run(main())
```

---

## Configuration

```python
md = MarkUDown(
    api_key="your-api-key",
    base_url="https://api.scrapetechnology.com",  # default
    timeout=120,          # HTTP request timeout (seconds)
    poll_interval=2.0,    # seconds between status checks for async jobs
    poll_timeout=300.0,   # max seconds to wait for a job to complete
)
```

All async endpoints accept `wait=False` to return the job ID immediately instead of polling:

```python
job = md.crawl("https://example.com", wait=False)
job_id = job["id"]

# Check later
status = md.get_job_status("crawl", job_id)
```

---

## API Reference

### `scrape(url, **opts)` → dict

Scrape a single URL. Returns result immediately.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | str | required | URL to scrape |
| `timeout` | int | 60 | Request timeout (seconds) |
| `exclude_tags` | list[str] | `["header","nav","footer"]` | HTML tags to strip |
| `main_content` | bool | True | Extract only main content |
| `include_links` | bool | False | Include hyperlinks in output |
| `include_html` | bool | False | Include raw HTML in output |

```python
result = md.scrape(
    "https://example.com",
    main_content=True,
    include_links=True,
)
print(result["markdown"])
```

---

### `screenshot(url, **opts)` → dict

Take a screenshot of a URL.

```python
result = md.screenshot("https://example.com")
# result["image"] contains base64-encoded PNG
```

---

### `map(url, **opts)` → dict

Discover all URLs on a website.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | str | required | Root URL |
| `allowed_words` | list[str] | [] | Only include URLs with these keywords |
| `blocked_words` | list[str] | [] | Exclude URLs with these keywords |
| `max_urls` | int | 1000 | Maximum URLs to return |
| `wait` | bool | True | Poll until complete |

```python
result = md.map("https://example.com", max_urls=500)
print(result["data"]["urls"])
```

---

### `crawl(url, **opts)` → dict

Crawl a website recursively and extract content from every page.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | str | required | Starting URL |
| `max_depth` | int | 2 | Maximum crawl depth |
| `limit` | int | 10 | Maximum pages to crawl |
| `timeout` | int | 60 | Per-page timeout |
| `include_links` | bool | False | Include links in output |
| `include_html` | bool | False | Include raw HTML |
| `blocked_words` | list[str] | [] | Skip URLs with these words |
| `include_only` | list[str] | [] | Only crawl URLs matching these patterns |
| `main_content` | bool | True | Extract only main content |
| `callback_url` | str | None | Webhook URL on completion |
| `wait` | bool | True | Poll until complete |

```python
result = md.crawl(
    "https://docs.example.com",
    max_depth=3,
    limit=50,
    include_only=["*guide*", "*tutorial*"],
)
for page in result["data"]["pages"]:
    print(page["url"], page["markdown"][:200])
```

---

### `extract(url, schema, **opts)` → dict

Schema-based structured data extraction with AI.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | str | required | URL to extract from |
| `schema` | list[dict] | required | Field definitions |
| `extract_query` | str | "" | Natural language description |
| `extraction_scope` | str | None | "whole_site", "category", "single_page" |
| `extraction_target` | str | None | Category or search term |
| `allowed_words` | list[str] | [] | Keywords in relevant URLs |
| `blocked_words` | list[str] | [] | Keywords in irrelevant URLs |
| `allowed_patterns` | list[str] | [] | URL path fragments to include |
| `blocked_patterns` | list[str] | [] | URL path fragments to exclude |
| `callback_url` | str | None | Webhook URL on completion |
| `wait` | bool | True | Poll until complete |

Schema field format: `{"name": "field_name", "type": "string|float|integer|date|url", "active": True}`

```python
result = md.extract(
    "https://shop.example.com",
    schema=[
        {"name": "title",  "type": "string", "active": True},
        {"name": "price",  "type": "float",  "active": True},
        {"name": "in_stock", "type": "string", "active": True},
    ],
    extract_query="Product listings with title, price and availability",
    extraction_scope="whole_site",
)
```

---

### `create_schema(query)` → dict

Generate an extraction schema automatically from a natural language description.

```python
schema_data = md.create_schema(
    "Extract all products from https://shop.example.com with title, price, rating and availability"
)
# Returns: {"url": "...", "schema": [...], "extraction_scope": "...", ...}
```

---

### `prompt_extract(url, prompt, **opts)` → dict

Extract data with a natural language prompt — no schema required.

```python
result = md.prompt_extract(
    "https://example.com/team",
    prompt="List all team members with their name, title and LinkedIn URL",
)
```

---

### `batch_scrape(urls, **opts)` → dict

Scrape multiple URLs in parallel.

```python
result = md.batch_scrape([
    "https://example.com/page-1",
    "https://example.com/page-2",
    "https://example.com/page-3",
])
for page in result["data"]["pages"]:
    print(page["url"])
```

---

### `search(query, **opts)` → dict

Web search with optional scraping of result pages.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | str | required | Search query |
| `limit` | int | 5 | Number of results |
| `scrape_results` | bool | True | Scrape each result page |
| `lang` | str | "en" | Language code |
| `country` | str | "us" | Country code |
| `engine` | str | "google" | "google", "bing", "duckduckgo", "all" |
| `timeout` | int | 60 | Timeout in seconds |
| `callback_url` | str | None | Webhook URL on completion |
| `wait` | bool | True | Poll until complete |

```python
result = md.search(
    "open source web scraping frameworks",
    engine="all",
    limit=10,
    scrape_results=True,
)
```

---

### `rss(url, **opts)` → dict

Generate an RSS feed from any web page.

```python
result = md.rss("https://blog.example.com", max_items=20, title="My Blog Feed")
print(result["data"]["feed_url"])
```

---

### `change_detection(url, **opts)` → dict

Detect and diff content changes on a page.

```python
result = md.change_detection("https://example.com/pricing", include_diff=True)
print(result["data"]["changed"])  # True/False
print(result["data"]["diff"])
```

---

### `deep_research(query, urls, **opts)` → dict

Scrape multiple pages and synthesize findings with an LLM.

```python
result = md.deep_research(
    query="What are the main pricing differences between these competitors?",
    urls=[
        "https://competitor-a.com/pricing",
        "https://competitor-b.com/pricing",
    ],
    max_tokens=4096,
)
print(result["data"]["synthesis"])
```

---

### `agent(url, prompt, **opts)` → dict

AI autonomous navigation agent that clicks, scrolls and fills forms.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | str | required | Starting URL |
| `prompt` | str | required | Task description |
| `max_steps` | int | 10 | Max actions |
| `max_pages` | int | 5 | Max pages to visit |
| `allow_navigation` | bool | True | Allow following links |
| `include_screenshots` | bool | False | Capture screenshots |
| `timeout` | int | 120 | Timeout in seconds |
| `wait` | bool | True | Poll until complete |

```python
result = md.agent(
    "https://example.com",
    prompt="Find the contact email on this website",
    max_steps=15,
)
print(result["data"]["answer"])
```

---

### `smart_extract(url, goal, **opts)` → dict

Guided extraction: analyzes the site structure, plans the interaction sequence, and returns complete data.

```python
result = md.smart_extract(
    "https://example.com/products",
    goal="Extract all products with name, price, and description",
    output_format="json",
    hints=["Click 'Load more' button to get all items"],
)
```

---

### `rank(keyword, domain, **opts)` → dict

Check where a domain ranks for a keyword in search results.

```python
result = md.rank(
    keyword="web scraping api",
    domain="scrapetechnology.com",
    engine="google",
    country="us",
    depth=100,
)
print(result["data"]["position"])  # e.g. 4
```

---

### `dataset(url, goal, **opts)` → dict

Auto-paginate a listing page and extract all items as a structured dataset.

```python
result = md.dataset(
    "https://books.toscrape.com",
    goal="Extract all books with title, price, rating and availability",
    max_pages=10,
    output_format="json",
)
print(len(result["data"]["items"]))
```

---

### Monitor

Create a persistent URL monitor that calls a webhook when content changes.

```python
# Create a monitor
subscription = md.monitor_create(
    "https://example.com/pricing",
    callback_url="https://yourapp.com/webhook",
    interval_minutes=60,
)
sub_id = subscription["subscription_id"]

# List active monitors
monitors = md.monitor_list()

# Delete a monitor
md.monitor_delete(sub_id)
```

---

### Job Management

```python
# Get status of any async job
status = md.get_job_status("crawl", "job-id-here")
# status["status"] → "pending" | "processing" | "completed" | "failed"

# Cancel a running job
md.cancel_job("agent", "job-id-here")
```

---

## Error Handling

```python
from markudown import MarkUDown, MarkUDownError, RateLimitError, InsufficientCreditsError

md = MarkUDown(api_key="your-key")

try:
    result = md.scrape("https://example.com")
except RateLimitError:
    print("Rate limit hit — wait a minute and retry")
except InsufficientCreditsError:
    print("Out of credits — upgrade at scrapetechnology.com")
except MarkUDownError as e:
    print(f"API error {e.status_code}: {e}")
```

---

## Context Manager

```python
with MarkUDown(api_key="your-key") as md:
    result = md.scrape("https://example.com")
# HTTP connection is automatically closed
```

---

## Links

- [Website](https://scrapetechnology.com/markudown)
- [Documentation](https://scrapetechnology.com/markudown/docs)
- [GitHub](https://github.com/Scrape-Technology/MarkUDown-Engine)
- [MCP Server](https://github.com/Scrape-Technology/markudown-mcp)
