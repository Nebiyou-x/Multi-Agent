"""Tool #4: Web Search.

Wraps the Tavily API (picked over Brave/SerpAPI: built for agent use - one
endpoint returns clean title/url/snippet results, and it has a generous free
tier for development). Results are cached on disk during dev so repeated or
re-planned queries don't burn API calls.

Config (env):
    TAVILY_API_KEY         - required for live search
    WEB_SEARCH_CACHE_TTL   - seconds a cached result stays fresh (default 24h)
    WEB_SEARCH_CACHE_DIR   - where to keep the cache (default .cache/web_search)
"""

import hashlib
import json
import os
import time
from pathlib import Path

import httpx

_DEFAULTS = {"max_results": 5}


def _cache_path() -> Path:
    d = Path(os.getenv("WEB_SEARCH_CACHE_DIR", ".cache/web_search"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(query: str, max_results: int) -> str:
    raw = f"{query.strip().lower()}|{max_results}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_get(key: str) -> dict | None:
    ttl = int(os.getenv("WEB_SEARCH_CACHE_TTL", 24 * 3600))
    f = _cache_path() / f"{key}.json"
    if not f.exists():
        return None
    try:
        rec = json.loads(f.read_text())
        if time.time() - rec.get("ts", 0) > ttl:
            f.unlink(missing_ok=True)
            return None
        rec["cached"] = True
        return rec
    except (json.JSONDecodeError, OSError):
        return None


def _cache_set(key: str, payload: dict) -> None:
    payload = {**payload, "cached": False, "ts": time.time()}
    (_cache_path() / f"{key}.json").write_text(json.dumps(payload, indent=1))


async def web_search(args: str | dict) -> dict:
    if isinstance(args, str):
        args = {"query": args}
    args = args or {}
    query = (args.get("query") or "").strip()
    if not query:
        return {"error": "web_search requires a 'query' argument"}
    max_results = int(args.get("max_results") or _DEFAULTS["max_results"])

    key = _cache_key(query, max_results)
    hit = _cache_get(key)
    if hit:
        return hit

    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return {"error": "TAVILY_API_KEY is not set - web_search is unavailable"}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": query, "max_results": max_results},
                headers={"User-Agent": "AgentPlatform/1.0"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        return {"error": f"web_search request failed: {type(e).__name__}: {e}", "query": query}

    results = [
        {"title": item.get("title", ""), "url": item.get("url", ""), "snippet": item.get("content", "")}
        for item in data.get("results", [])[:max_results]
    ]
    payload = {"query": query, "results": results, "source": "tavily", "cached": False}
    _cache_set(key, payload)
    return payload
