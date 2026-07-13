"Beacon v0.15 — External API Client."
import hashlib, json, logging, requests
from django.conf import settings
from django.core.cache import cache
logger = logging.getLogger("beacon.external")

def get_related_articles(query, max_results=5):
    cache_key = f"related_articles:{hashlib.md5(query.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached is not None: return json.loads(cached)
    try:
        r = requests.get("https://api.newsapi.example/v2/everything", params={"q":query,"pageSize":max_results,"apiKey":settings.NEWS_API_KEY}, timeout=0.2)
        r.raise_for_status()
        articles = [{"title":i.get("title",""),"url":i.get("url",""),"snippet":i.get("description","")} for i in r.json().get("articles",[])[:max_results]]
    except: articles = []
    cache.set(cache_key, json.dumps(articles), timeout=900)
    return articles
