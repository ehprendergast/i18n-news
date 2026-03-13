"""Web search and content extraction for the i18n news pipeline.

Uses DuckDuckGo for multilingual search and trafilatura for article extraction.
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional
from urllib.parse import urlparse

import httpx
import trafilatura
from duckduckgo_search import DDGS


SEARCH_TOPICS = ["politics", "economics", "culture", "society"]
RESULTS_PER_QUERY = 8


def _is_blocked(url: str, blocklist: set[str]) -> bool:
    """Check if a URL's domain is in the blocklist."""
    try:
        domain = urlparse(url).netloc.lower()
        # Check domain and parent domain
        parts = domain.split(".")
        for i in range(len(parts) - 1):
            check = ".".join(parts[i:])
            if check in blocklist:
                return True
    except Exception:
        pass
    return False


def search_country_news(
    country: str,
    languages: list[str],
    region: str,
    blocklist: set[str],
    days: int = 30,
    translated_queries: Optional[dict] = None,
) -> list[dict]:
    """Search DuckDuckGo for country news in each language.

    Returns list of dicts with keys: url, title, snippet, language, topic.
    """
    seen_urls = set()
    results = []

    for lang in languages:
        for topic in SEARCH_TOPICS:
            if lang.lower() == "english":
                query = f"{country} {topic} news"
            elif translated_queries and lang in translated_queries:
                # Use translated base + English topic for specificity
                query = f"{translated_queries[lang]} {topic}"
            else:
                query = f"{country} {topic} news {lang}"

            try:
                with DDGS() as ddgs:
                    search_results = ddgs.text(
                        query,
                        region=region,
                        max_results=RESULTS_PER_QUERY,
                        timelimit=f"m" if days <= 30 else None,
                    )
            except Exception as e:
                print(f"  Search failed for '{query}': {e}")
                search_results = []

            for r in search_results:
                url = r.get("href", r.get("link", ""))
                if not url or url in seen_urls:
                    continue
                if _is_blocked(url, blocklist):
                    continue
                seen_urls.add(url)
                results.append({
                    "url": url,
                    "title": r.get("title", ""),
                    "snippet": r.get("body", r.get("snippet", "")),
                    "language": lang,
                    "topic": topic,
                })

            # Rate limiting to avoid DuckDuckGo throttling
            time.sleep(1)

    return results


async def extract_articles(
    search_results: list[dict],
    max_concurrent: int = 5,
) -> list[dict]:
    """Extract article text from URLs using trafilatura.

    Returns the search_results list enriched with 'content' field.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_one(item: dict) -> dict:
        async with semaphore:
            url = item["url"]
            try:
                async with httpx.AsyncClient(
                    timeout=15.0,
                    follow_redirects=True,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        )
                    },
                ) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    html = resp.text

                text = trafilatura.extract(
                    html,
                    include_comments=False,
                    include_tables=False,
                    favor_recall=True,
                )
                item["content"] = text or ""
            except Exception as e:
                item["content"] = ""
                item["extraction_error"] = str(e)
            return item

    tasks = [fetch_one(item) for item in search_results]
    return await asyncio.gather(*tasks)
