
"""Beacon v0.7 — External API Client. Unchanged from Ch5-6."""
import hashlib, json, logging
import requests
from django.conf import settings
from django.core.cache import cache
logger = logging.getLogger("beacon.external")


def get_related_articles(query: str, max_results: int = 5) -> list[dict]:
    cache_key = f"related_articles:{hashlib.md5(query.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return json.loads(cached)
    try:
        response = requests.get("https://api.newsapi.example/v2/everything", params={"q": query, "pageSize": max_results, "apiKey": settings.NEWS_API_KEY}, timeout=0.2)
        response.raise_for_status()
        articles = _parse_articles(response.json(), max_results)
    except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
        logger.warning("External API call failed for query=%r: %s", query, exc)
        articles = []
    cache.set(cache_key, json.dumps(articles), timeout=900)
    return articles


def _parse_articles(data: dict, max_results: int) -> list[dict]:
    return [{"title": item.get("title", ""), "url": item.get("url", ""), "snippet": item.get("description", "")} for item in data.get("articles", [])[:max_results]]
