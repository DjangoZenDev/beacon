"""
Beacon v0.4 — External API Client

Chapter 4 introduces a cached external API call for "related articles".
This is Fix 2 from the chapter: the synchronous HTTP call in the request
path is wrapped with Redis caching and a 200ms timeout.

Design decisions (Maya's Option C + B):
- Cache with a 15-minute TTL: most page views hit the cache and never
  touch the external API. Cache hits return from Redis in <2ms.
- 200ms timeout on HTTP calls: a cache miss with a fast API returns in
  50-100ms. A slow API times out at 200ms and renders the placeholder.
- Cache empty results too: if the API is unreachable, we cache the
  empty list to avoid repeatedly hitting a failing API.

Costs:
- Staleness: articles from 14 minutes ago might miss a just-published
  article. For Beacon's use case (knowledge tool), this is acceptable.
- Blocked workers: a cache miss with a 200ms timeout still blocks a
  gunicorn worker for up to 200ms. At high concurrency, this adds up.
  Chapter 6 addresses this with async views (Django 5.1+ async support).
"""

import hashlib
import json
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("beacon.external")


def get_related_articles(query: str, max_results: int = 5) -> list[dict]:
    """
    Fetch related articles for a search query from an external API.

    Results are cached for 15 minutes to avoid blocking gunicorn workers
    on synchronous HTTP calls. A 200ms timeout prevents slow API
    responses from cascading into request timeouts.

    Args:
        query: The search query (typically a page title).
        max_results: Maximum number of articles to return.

    Returns:
        A list of article dicts with 'title', 'url', and 'snippet' keys.
        Returns an empty list if the API is unreachable or times out.
    """
    cache_key = f"related_articles:{hashlib.md5(query.encode()).hexdigest()}"

    # Try the cache first.
    cached = cache.get(cache_key)
    if cached is not None:
        return json.loads(cached)

    # Cache miss: call the external API with a tight timeout.
    try:
        response = requests.get(
            "https://api.newsapi.example/v2/everything",
            params={
                "q": query,
                "pageSize": max_results,
                "apiKey": settings.NEWS_API_KEY,
            },
            timeout=0.2,  # 200 milliseconds
        )
        response.raise_for_status()
        articles = _parse_articles(response.json(), max_results)

    except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
        logger.warning("External API call failed for query=%r: %s", query, exc)
        articles = []

    # Cache the result — even an empty list — to avoid repeatedly
    # hitting a failing API.
    cache.set(cache_key, json.dumps(articles), timeout=900)  # 15 minutes

    return articles


def _parse_articles(data: dict, max_results: int) -> list[dict]:
    """Parse the external API response into a uniform format."""
    articles = []
    for item in data.get("articles", [])[:max_results]:
        articles.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("description", ""),
        })
    return articles
